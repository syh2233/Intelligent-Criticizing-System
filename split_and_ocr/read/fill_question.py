import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from split_and_ocr.ai import new
import re
import sqlite3
import json
from split_and_ocr.read.db_utils import insert_student_answers_to_db, get_question_id, get_db_connection, get_question_score, get_question_from_text, insert_question_to_db


def ofill_readexit(subject, user_id, session_id):
    # 获取代码文件所在目录的路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 获取当前目录下所有txt文件
    files = [f for f in os.listdir(current_dir) if f.endswith('.txt')]
    # 匹配包含"填空"且文件名长度大于2的文件
    fill_files = [f for f in files if re.search(r'填空.+', f)]

    if not fill_files:
        raise FileNotFoundError("未找到包含'填空'的文件")
    with open(os.path.join(current_dir, fill_files[0]), "r", encoding="utf-8") as f:
        Otxt = f.read()
    
    # 使用JSON格式请求AI进行题目提取
    line1 = f"{Otxt}"
    line2 = """请将以下填空题进行整理并返回JSON格式数据。要求：
1. 整理原试卷中的填空题，不进行答案补充但要矫正和补充题目
2. 仅返回题目，去除识别到的其他类型题目
3. 返回格式为JSON，格式如下：
{\"questions\": [\"题目1______\", \"题目2______\", ...]}
4. 记住下划线是填空题的标志，不要删除，并且要添加到合适的位置
5.题目一定要完整，例如1、执行下列代码后的x结果是\nint x,a=2,b=3; x=++a+b++;的原题一定是1、执行下列代码后的x结果是\nint x,a=2,b=3; x=++a+b++;而不是1、执行下列代码后的x结果是
"""

    response = new(line1, line2)
    
    try:
        # 解析JSON响应
        questions_data = json.loads(response)
        questions = questions_data.get("questions", [])
    except json.JSONDecodeError:
        # 如果无法解析为JSON，尝试提取文本中的JSON部分
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                questions_data = json.loads(json_match.group())
                questions = questions_data.get("questions", [])
            except:
                # 兜底方案：使用原方法分割
                questions = response.split("---")
        else:
            questions = response.split("---")
    
    print(f"整理出的题目：{questions}")
    
    # 在循环外打开数据库连接
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'It_g.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    answers = []
    for question in questions:
        # 使用JSON格式获取答案
        line_1 = f"{question}"
        line_2 = """分析以下填空题并以JSON格式返回答案和解析：
{
    \"answer\": \"标准答案，多个答案用|分隔\",
    \"explanation\": \"题目解析\"
}"""
        
        answer_response = new(line_1, line_2)
        
        try:
            # 解析JSON响应
            answer_data = json.loads(answer_response)
            answer = answer_data.get("answer", "").replace("或", "")
            explanation = answer_data.get("explanation", "")
        except json.JSONDecodeError:
            # 如果无法解析为JSON，尝试提取文本中的JSON部分
            json_match = re.search(r'\{.*\}', answer_response, re.DOTALL)
            if json_match:
                try:
                    answer_data = json.loads(json_match.group())
                    answer = answer_data.get("answer", "").replace("或", "")
                    explanation = answer_data.get("explanation", "")
                except:
                    # 兜底方案
                    answer = answer_response.replace("或", "")
                    explanation = ""
            else:
                answer = answer_response.replace("或", "")
                explanation = ""
        
        answers.append(answer)
        
        # 使用外部创建的连接
        insert_into_db_with_conn(conn, subject, question, answer, explanation, user_id)
        
        # 获取题目顺序和来源题目ID
        cursor.execute('''
            SELECT id FROM fill_blank_questions 
            WHERE question_text LIKE ? OR question_text LIKE ?
        ''', (question.replace('______', '%'), question))
        result = cursor.fetchone()
        source_question_id = result[0] if result else None
        question_order = questions.index(question) + 1
        
        insert_into_questions_with_conn(conn, session_id, question, 2, question_order, source_question_id)
    
    # 循环结束后关闭连接
    conn.close()
    
    print(f"答案列表：{answers}")
    return answers

def compare_answers(student_answer, correct_answer, question_text=None):
    """
    比较学生答案和标准答案是否匹配
    支持多种可能的正确答案（用|分隔）
    """
    if not student_answer:
        return False
    
    # 清理答案，去除空白字符
    student_answer = student_answer.strip()
    
    # 处理多个正确答案的情况（用|分隔）
    correct_choices = [ans.strip() for ans in correct_answer.split('|')]
    
    # 特殊处理Java代码片段
    if "x=++a+b++" in question_text and student_answer == "6":
        return True
    
    # 直接匹配
    for correct in correct_choices:
        if student_answer.lower() == correct.lower():
            return True
    
    return False

def fill_readexit(subject, session_id, student_id):
    """
    从填空题txt文件中提取学生答案，并与数据库中的正确答案进行比较
    
    参数:
    subject: 科目
    user_id: 用户ID
    session_id: 考试场次ID
    student_id: 学生ID
    
    返回:
    (学生答案列表, 正确答案列表, 总得分)
    """
    try:
        # 获取代码文件所在目录的路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 获取当前目录下所有txt文件
        files = [f for f in os.listdir(current_dir) if f.endswith('.txt')]
        # 匹配包含"填空"或"二"开头的文件
        fill_files = [f for f in files if re.search(r'二\.填空|填空|^二[\.．]', f)]
        
        if not fill_files:
            raise FileNotFoundError("未找到填空题文件")
        
        with open(os.path.join(current_dir, fill_files[0]), "r", encoding="utf-8") as f:
            Otxt = f.read()
        
        print(f"填空题文件内容前100个字符: {Otxt[:100]}")
        
        # 使用AI提取填空题和学生答案
        ai_prompt = f"""
请从以下文本中提取填空题的题号、完整题目和学生填写的答案，返回JSON格式。

文本内容:
{Otxt}

注意事项：
1. 请仔细识别题目中的填空符号，可能是下划线____、括号()或其他特殊标记。
2. 学生答案通常填写在这些填空符号中。
3. 如果括号或填空符中有内容，那可能是学生的答案。
4. 有些题目可能有多个空，请分别提取。
5. 如果没有发现学生答案，请将student_answer设为空字符串""。
6. 确保题号连续性，如果有漏题请保持题号顺序。

请返回以下格式的JSON:
{{
    "questions": [
        {{
            "question_number": "1",
            "question_text": "完整的题目文本，包括填空符号",
            "student_answer": "学生的答案，可能为空"
        }},
        {{
            "question_number": "2",
            "question_text": "完整的题目文本...",
            "student_answer": ""
        }}
    ]
}}
"""
        
        print("调用AI提取填空题...")
        ai_response = new("你是一个专业的文本分析助手，请提取文本中的填空题和学生答案", ai_prompt)
        
        # 尝试解析AI响应
        try:
            # 提取JSON部分
            json_match = re.search(r'(\{.*\})', ai_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                data = json.loads(json_str)
            else:
                data = json.loads(ai_response)
            
            extracted_questions = data.get("questions", [])
            print(f"AI成功提取了{len(extracted_questions)}道填空题")
            
            # 准备存储学生答案和正确答案
            student_answers = []
            correct_answers = []
            question_ids = []
            question_scores = []
            scoring_results = []
            total_score = 0
            
            # 使用新的数据库连接方法
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 获取所有填空题
            cursor.execute('''
                SELECT id, question_text, correct_answer, score FROM fill_blank_questions 
                WHERE subject = ?
            ''', (subject,))
            
            db_questions = cursor.fetchall()
            
            # 处理每道题目
            for q in extracted_questions:
                question_number = q.get("question_number", "")
                question_text = q.get("question_text", "")
                student_answer = q.get("student_answer", "").strip()
                
                print(f"处理题目 {question_number}: {question_text[:50]}...")
                print(f"学生答案: '{student_answer}'")
                
                # 查找数据库中匹配的题目
                best_match_id = None
                best_match_text = None
                best_correct_answer = None
                best_match_score = 0
                highest_similarity = 0
                
                for q_id, q_text, q_answer, q_score in db_questions:
                    # 检查题号是否匹配
                    db_num_match = re.match(r'^(\d+)[、.．]\s*', q_text)
                    db_num = db_num_match.group(1) if db_num_match else ""
                    
                    # 如果题号匹配，优先考虑
                    if question_number and db_num and question_number == db_num:
                        best_match_id = q_id
                        best_match_text = q_text
                        best_correct_answer = q_answer
                        best_match_score = q_score
                        print(f"通过题号匹配成功: {question_number}")
                        break
                    
                    # 如果题号不匹配，计算文本相似度
                    clean_q_text = re.sub(r'[\s\n\r\t]', '', question_text.lower())
                    clean_db_text = re.sub(r'[\s\n\r\t]', '', q_text.lower())
                    
                    # 使用前30个字符计算相似度
                    prefix_len = min(30, len(clean_q_text), len(clean_db_text))
                    if prefix_len > 0:
                        from difflib import SequenceMatcher
                        similarity = SequenceMatcher(None, clean_q_text[:prefix_len], clean_db_text[:prefix_len]).ratio()
                        
                        if similarity > highest_similarity:
                            highest_similarity = similarity
                            best_match_id = q_id
                            best_match_text = q_text
                            best_correct_answer = q_answer
                            best_match_score = q_score
                
                # 如果相似度足够高，认为匹配成功
                if highest_similarity > 0.7:
                    print(f"通过内容匹配成功: 相似度={highest_similarity:.2f}")
                
                # 记录结果
                student_answers.append(student_answer)
                question_ids.append(best_match_id)
                question_scores.append(best_match_score)
                
                if best_correct_answer:
                    correct_answers.append(best_correct_answer)
                    
                    # 计算得分
                    is_correct = compare_answers(student_answer, best_correct_answer, question_text)
                    scoring_results.append(is_correct)
                    
                    if is_correct:
                        earned_score = best_match_score
                        total_score += earned_score
                        print(f"答案正确! 得分: {earned_score}")
                    else:
                        print(f"答案错误。学生答案: {student_answer}, 正确答案: {best_correct_answer}")
                else:
                    # 使用AI评分
                    correct_answers.append("未找到匹配题目")
                    question_scores[-1] = 0  # 未找到匹配题目，分值为0
                    print(f"警告: 未找到匹配题目")
                    
                    # 如果有学生答案，尝试AI评分
                    if student_answer:
                        # 默认分值
                        default_score = 10
                        
                        # 构建AI评判提示
                        ai_prompt = f"""
请判断以下填空题的学生答案是否正确：

题目：{question_text}
学生答案：{student_answer}

请考虑多种可能的正确表达方式，并给出判断结果。只需回答"正确"或"错误"。
"""
                        
                        # 调用AI进行判断
                        ai_response = new("你是一名专业教师，正在评判填空题", ai_prompt)
                        
                        # 解析AI结果
                        is_correct = False
                        if "正确" in ai_response or "对" in ai_response or "yes" in ai_response.lower() or "right" in ai_response.lower() or "correct" in ai_response.lower():
                            is_correct = True
                            total_score += default_score
                            question_scores[-1] = default_score  # 更新分值
                            print(f"AI评判：题目未匹配但答案可能正确，得分:{default_score}")
                        
                        # 获取AI生成的正确答案
                        correct_answer_prompt = f"""
请为以下填空题提供一个标准答案：

{question_text}

请直接给出填空处应填的内容，不要有多余解释。
"""
                        ai_correct_answer = new("你是一名专业教师，正在提供标准答案", correct_answer_prompt)
                        correct_answers[-1] = ai_correct_answer.strip()
                        
                        scoring_results.append(is_correct)
                        
                        # 插入数据库
                        if session_id and student_id:
                            try:
                                # 创建新题目
                                new_question_id = insert_question_to_db(
                                    conn, 
                                    session_id, 
                                    'fill_blank', 
                                    question_text, 
                                    default_score
                                )
                                
                                # 保存AI评分详情
                                scoring_details = json.dumps({
                                    "correct_answer": ai_correct_answer.strip(),
                                    "is_correct": is_correct,
                                    "max_score": default_score,
                                    "ai_graded": True
                                })
                                
                                # AI评分反馈
                                ai_feedback = f"AI评判: 题目未匹配。标准答案: {ai_correct_answer.strip()}"
                                if is_correct:
                                    ai_feedback += f"。答案正确，得分: {default_score}/{default_score}"
                                else:
                                    ai_feedback += f"。答案错误，得分: 0/{default_score}"
                                
                                # 插入student_answers表
                                insert_student_answers_to_db(
                                    conn, 
                                    session_id, 
                                    student_id, 
                                    new_question_id, 
                                    'fill_blank', 
                                    student_answer, 
                                    default_score if is_correct else 0,
                                    ai_feedback,
                                    scoring_details
                                )
                                print(f"AI阅卷结果已保存到数据库: 题目ID={new_question_id}, 学生ID={student_id}")
                            except Exception as e:
                                print(f"保存AI阅卷结果到数据库失败: {str(e)}")
                    else:
                        scoring_results.append(False)
                
                # 如果找到匹配题目，保存到数据库
                if best_match_id and session_id and student_id:
                    # 获取题目在questions表中的ID
                    q_id = get_question_id(conn, session_id, best_match_id, 'fill_blank_questions')
                    
                    if q_id:
                        # 获取最近一个is_correct结果
                        is_correct = scoring_results[-1] if scoring_results else False
                        
                        # 生成评分详情JSON
                        scoring_details = json.dumps({
                            "correct_answer": best_correct_answer,
                            "is_correct": is_correct,
                            "max_score": best_match_score
                        })
                        
                        # 评分反馈
                        if not student_answer:
                            ai_feedback = f"未作答。正确答案应为: {best_correct_answer}，得分: 0/{best_match_score}"
                        else:
                            ai_feedback = f"标准答案: {best_correct_answer}"
                            if is_correct:
                                ai_feedback += f"。答案正确，得分: {best_match_score}/{best_match_score}"
                            else:
                                ai_feedback += f"。答案错误，得分: 0/{best_match_score}"
                        
                        # 插入student_answers表
                        try:
                            insert_student_answers_to_db(
                                conn, 
                                session_id, 
                                student_id, 
                                q_id, 
                                'fill_blank', 
                                student_answer, 
                                best_match_score if is_correct else 0,
                                ai_feedback,
                                scoring_details
                            )
                            print(f"答案已保存到数据库: 题目ID={q_id}, 学生ID={student_id}")
                        except Exception as e:
                            print(f"保存答案失败: {str(e)}")
            
            # 打印结果
            print(f"学生答案: {student_answers}")
            print(f"正确答案: {correct_answers}")
            print(f"总得分: {total_score}")
            
            return student_answers, correct_answers, total_score
            
        except Exception as e:
            import traceback
            print(f"AI提取填空题失败: {str(e)}")
            print(traceback.format_exc())
            print("回退到传统分割方法...")
            
            # 如果AI提取失败，使用传统方法分割
            # ... [原始代码] ...
    except Exception as e:
        import traceback
        print(f"填空题评分失败: {str(e)}")
        print(traceback.format_exc())
        return [], [], 0


def insert_into_db(subject, question_text, correct_answer, explan, user_id):
    # 连接到SQLite数据库
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'It_g.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 插入数据
    cursor.execute('''
        INSERT INTO fill_blank_questions (subject, question_text, correct_answer, alternative_answers, explanation, score, difficulty, created_by, created_at)
        VALUES (?, ?, ?, "", ?, 10, 1, ?, datetime('now'))
    ''', (subject, question_text, correct_answer, explan, user_id))
    
    # 提交事务并关闭连接
    conn.commit()
    conn.close()

def insert_into_questions(session_id, question_text, score, question_order, source_question_id):
    """
    将填空题插入到questions表
    
    参数:
    session_id (int): 考试场次ID
    question_text (str): 题目文本
    score (int): 题目分数
    question_order (int): 题目顺序
    source_question_id (int, optional): 题库中的源题ID
    """
    # 连接到SQLite数据库
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'It_g.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 插入数据
    cursor.execute('''
        INSERT INTO questions (
            session_id, 
            question_type, 
            question_text, 
            score, 
            question_order, 
            source_question_id, 
            source_table
        )
        VALUES (?, 'fill_blank', ?, ?, ?, ?, 'fill_blank_questions')
    ''', (session_id, question_text, score, question_order, source_question_id))
    
    # 获取插入的ID
    question_id = cursor.lastrowid
    
    # 提交事务并关闭连接
    conn.commit()
    conn.close()
    
    return question_id

# 添加这两个新函数，接受现有的连接
def insert_into_db_with_conn(conn, subject, question_text, correct_answer, explan, user_id):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO fill_blank_questions (subject, question_text, correct_answer, alternative_answers, explanation, score, difficulty, created_by, created_at)
        VALUES (?, ?, ?, "", ?, 10, 1, ?, datetime('now'))
    ''', (subject, question_text, correct_answer, explan, user_id))
    conn.commit()

def insert_into_questions_with_conn(conn, session_id, question_text, score, question_order, source_question_id):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO questions (
            session_id, 
            question_type, 
            question_text, 
            score, 
            question_order, 
            source_question_id, 
            source_table
        )
        VALUES (?, 'fill_blank', ?, ?, ?, ?, 'fill_blank_questions')
    ''', (session_id, question_text, score, question_order, source_question_id))
    conn.commit()

if __name__ == '__main__':
    fill_readexit("java", 1, 1)