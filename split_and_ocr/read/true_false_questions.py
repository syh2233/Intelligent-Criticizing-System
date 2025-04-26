import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from split_and_ocr.ai import new
import re
import sqlite3
import json
from split_and_ocr.read.db_utils import insert_student_answers_to_db, get_question_id, get_db_connection, get_question_score, get_question_from_text, insert_question_to_db

def tf_readexit(subject, user_id, session_id):
    # 获取代码文件所在目录的路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 获取当前目录下所有txt文件
    files = [f for f in os.listdir(current_dir) if f.endswith('.txt')]
    # 匹配包含"判断"且文件名长度大于2的文件
    fill_files = [f for f in files if re.search(r'判断.+', f)]

    if not fill_files:
        raise FileNotFoundError("未找到包含'判断'的文件")
    with open(os.path.join(current_dir, fill_files[0]), "r", encoding="utf-8") as f:
        Otxt = f.read()
    
    # 使用JSON格式请求AI进行题目提取
    line1 = f"{Otxt}"
    line2 = """请将以下判断题进行整理并返回JSON格式数据。要求：
1. 整理原试卷中的判断题，不进行答案补充但要矫正和补充题目
2. 仅返回题目，去除识别到的其他类型题目
3. 返回格式为JSON，格式如下：
{\"questions\": [\"题目1\", \"题目2\", ...]}"""

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
                questions = [q.strip() for q in response.split("---") if q.strip()]
        else:
            questions = [q.strip() for q in response.split("---") if q.strip()]
    
    print(f"整理出的题目：{questions}")
    
    # 在循环外打开数据库连接
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'It_g.db')
    conn = sqlite3.connect(db_path)
    
    original_answers = []
    answers = []
    for i, question in enumerate(questions):
        # 使用JSON格式获取答案
        line_1 = f"{question}"
        line_2 = """分析以下判断题并以JSON格式返回答案和解析：
{
    \"answer\": \"正确答案，只能是'对'或'错'\",
    \"explanation\": \"题目解析\"
}"""
        
        answer_response = new(line_1, line_2)
        
        try:
            # 解析JSON响应
            answer_data = json.loads(answer_response)
            answer = answer_data.get("answer", "").strip()
            # 确保答案是"对"或"错"
            if answer not in ["对", "错"]:
                answer = "对" if "对" in answer or "正确" in answer or "true" in answer.lower() else "错"
            explanation = answer_data.get("explanation", "")
        except json.JSONDecodeError:
            # 如果无法解析为JSON，尝试提取文本中的JSON部分
            json_match = re.search(r'\{.*\}', answer_response, re.DOTALL)
            if json_match:
                try:
                    answer_data = json.loads(json_match.group())
                    answer = answer_data.get("answer", "").strip()
                    if answer not in ["对", "错"]:
                        answer = "对" if "对" in answer or "正确" in answer or "true" in answer.lower() else "错"
                    explanation = answer_data.get("explanation", "")
                except:
                    # 兜底方案
                    answer = "对" if "对" in answer_response or "正确" in answer_response or "true" in answer_response.lower() else "错"
                    explanation = ""
            else:
                answer = "对" if "对" in answer_response or "正确" in answer_response or "true" in answer_response.lower() else "错"
                explanation = ""
        
        answers.append(answer)
        
        # 提取括号内的内容（如果有）作为原始答案
        bracket_match = re.search(r'\（(.*?)\）|\((.*?)\)', question)
        if bracket_match:
            orig_answer = bracket_match.group(1) if bracket_match.group(1) else bracket_match.group(2)
            original_answers.append(orig_answer)
        else:
            original_answers.append("")
        
        # 使用当前连接插入数据库
        question_id = insert_into_db_with_conn(conn, subject, question, answer, explanation, user_id)
        
        # 如果提供了session_id，则插入questions表
        if session_id:
            question_order = i + 1
            insert_into_questions_with_conn(conn, session_id, question, 3, question_order, question_id)
    
    # 关闭数据库连接
    conn.close()
    
    print(f"答案列表：{answers}")
    return original_answers, answers


def insert_into_db_with_conn(conn, subject, question_text, correct_answer, explanation, user_id):
    """插入判断题到true_false_questions表并返回插入的ID"""
    cursor = conn.cursor()
    
    # 将对错答案转换为布尔值存储
    is_correct = 1 if correct_answer == "对" else 0
    
    # 插入数据
    cursor.execute('''
        INSERT INTO true_false_questions 
        (subject, question_text, correct_answer, explanation, score, difficulty, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    ''', (subject, question_text, is_correct, explanation, 3, 3, user_id))
    
    # 获取插入的ID
    question_id = cursor.lastrowid
    conn.commit()
    
    return question_id


def insert_into_questions_with_conn(conn, session_id, question_text, score, question_order, source_question_id):
    """
    将判断题插入到questions表
    
    参数:
    session_id (int): 考试场次ID
    question_text (str): 题目文本
    score (int): 题目分数
    question_order (int): 题目顺序
    source_question_id (int): 题库中的源题ID
    """
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
        VALUES (?, 'true_false', ?, ?, ?, ?, 'true_false_questions')
    ''', (session_id, question_text, score, question_order, source_question_id))
    
    conn.commit()
    return cursor.lastrowid


def tf_grading(subject, session_id, student_id):
    """
    从判断题txt文件中提取学生答案，并与数据库中的正确答案进行比较
    返回：(学生答案列表, 正确答案列表, 总得分)
    """
    try:
        # 获取代码文件所在目录的路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 获取当前目录下所有txt文件
        files = [f for f in os.listdir(current_dir) if f.endswith('.txt')]
        # 匹配包含"判断"且文件名长度大于2的文件
        tf_files = [f for f in files if re.search(r'判断.+', f)]

        if not tf_files:
            raise FileNotFoundError("未找到包含'判断'的文件")
        
        # 读取文件内容
        with open(os.path.join(current_dir, tf_files[0]), "r", encoding="utf-8") as f:
            Otxt = f.read()
        
        # 提取所有判断题和学生答案
        questions = []
        student_answers = []
        
        # 使用正则表达式提取题目和括号内的答案
        pattern = r'\d+、（\s*([对错√×✓✗]?)\s*）(.*?)(?=\d+、|\Z)'
        matches = re.findall(pattern, Otxt, re.DOTALL)
        
        if not matches:
            # 如果没有匹配到，尝试其他格式
            pattern = r'\d+[\.、]?\s*\(([对错√×✓✗]?)\)(.*?)(?=\d+[\.、]|\Z)'
            matches = re.findall(pattern, Otxt, re.DOTALL)
        
        # 如果仍然没有匹配到，尝试通过换行符分割并查找括号
        if not matches:
            lines = Otxt.split('\n')
            for line in lines:
                if re.match(r'\d+', line.strip()):  # 以数字开头的行
                    # 提取括号内内容和题目文本
                    bracket_match = re.search(r'[（\(]\s*([对错√×✓✗]?)\s*[）\)]', line)
                    if bracket_match:
                        answer = bracket_match.group(1)
                        # 提取题目文本（括号后的内容）
                        text_match = re.search(r'[）\)]\s*(.*)', line)
                        text = text_match.group(1) if text_match else ""
                        matches.append((answer, text))
        
        # 处理提取的内容
        for answer, text in matches:
            # 清理和规范化学生答案
            clean_answer = answer.strip()
            if clean_answer in ['√', '✓']:
                clean_answer = '对'
            elif clean_answer in ['×', '✗']:
                clean_answer = '错'
            
            questions.append(text.strip())
            student_answers.append(clean_answer)
        
        # 使用新的数据库连接方法
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取所有判断题
        cursor.execute('''
            SELECT id, question_text, correct_answer, score FROM true_false_questions 
            WHERE subject = ?
        ''', (subject,))
        
        db_questions = cursor.fetchall()
        
        # 匹配题目和计算得分
        correct_answers = []
        total_score = 0
        scores = []
        question_ids = []  # 记录匹配到的题目ID
        is_correct_list = []  # 记录每题是否正确
        max_scores = []  # 每题的最高分值
        
        for i, (q_text, student_answer) in enumerate(zip(questions, student_answers)):
            # 找到最匹配的题目
            best_match = None
            highest_similarity = 0
            
            for db_q in db_questions:
                q_id, db_q_text, db_correct, source_score = db_q
                
                # 清理文本以便比较
                clean_q_text = re.sub(r'\s+', ' ', q_text).lower()
                clean_db_q_text = re.sub(r'\s+', ' ', db_q_text).lower()
                
                # 计算相似度 - 使用关键词匹配
                keywords = set(re.findall(r'\b\w+\b', clean_q_text))
                db_keywords = set(re.findall(r'\b\w+\b', clean_db_q_text))
                
                if keywords and db_keywords:
                    # 计算关键词重合度
                    common_words = keywords.intersection(db_keywords)
                    similarity = len(common_words) / max(len(keywords), len(db_keywords))
                    
                    # 提升特定关键词的权重
                    for keyword in ["基本数据类型", "byte", "int", "命令提示符", "编译", "java"]:
                        if keyword in clean_q_text and keyword in clean_db_q_text:
                            similarity += 0.2
                    
                    if similarity > highest_similarity:
                        highest_similarity = similarity
                        best_match = db_q
            
            # 找到匹配题目后评分
            if best_match and highest_similarity > 0.3:  # 至少30%相似度
                q_id, db_q_text, db_correct, source_score = best_match
                question_ids.append(q_id)
                
                # 从questions表获取该题的分数
                question_score = get_question_score(conn, session_id, q_id, 'true_false_questions')
                
                if question_score is not None:
                    print(f"从questions表获取到分数: {question_score} (源题ID: {q_id})")
                    max_score = question_score
                else:
                    # 如果在questions表中找不到该题，尝试通过题目文本匹配
                    q_id, q_score = get_question_from_text(conn, session_id, q_text, 'true_false')
                    if q_id and q_score:
                        max_score = q_score
                        print(f"通过文本匹配在questions表中找到题目: ID={q_id}, 分数={q_score}")
                    else:
                        # 如果找不到，使用源表中的分数
                        max_score = source_score
                        print(f"使用源表分数: {source_score} (未在questions表中找到匹配题目)")
                
                max_scores.append(max_score)
                
                # 将数据库布尔值转换为"对"/"错"
                correct_answer = "对" if db_correct else "错"
                correct_answers.append(correct_answer)
                
                # 评分
                is_correct = False
                if student_answer:  # 如果学生有作答
                    if student_answer == correct_answer:
                        total_score += max_score
                        scores.append(max_score)
                        is_correct = True
                    else:
                        scores.append(0)
                else:  # 学生未作答
                    scores.append(0)
                    
                is_correct_list.append(is_correct)
            else:
                # 如果没有找到匹配的题目，使用AI评估
                correct_answer = "未找到匹配题目"
                correct_answers.append(correct_answer)
                scores.append(0)
                question_ids.append(None)
                max_scores.append(3)  # 默认判断题3分
                is_correct = False
                default_score = 3  # 默认判断题分值
                
                # 使用AI直接评估（改进功能）
                if q_text:
                    ai_prompt = f"""
请分析以下判断题并给出标准答案：

题目: {q_text}

请判断题目表述是对还是错，只回答"对"或"错"，不要有任何解释。
"""
                    standard_answer = new("你是一名专业教师，正在提供标准答案", ai_prompt)
                    
                    # 解析AI返回的标准答案
                    if "对" in standard_answer or "正确" in standard_answer or "true" in standard_answer.lower():
                        correct_answer = "对"
                    else:
                        correct_answer = "错"
                    
                    # 更新正确答案
                    correct_answers[-1] = correct_answer
                    
                    # 如果学生有作答，评判是否正确
                    if student_answer:
                        is_correct = student_answer == correct_answer
                        if is_correct:
                            total_score += default_score
                            scores[-1] = default_score
                            print(f"AI评判：题目未匹配但学生答案正确，得分:{default_score}")
                    
                    # 如果提供了session_id和student_id，插入数据库 - 新增
                    if session_id and student_id:
                        try:
                            # 1. 首先在questions表中创建新题目
                            new_question_id = insert_question_to_db(
                                conn, 
                                session_id, 
                                'true_false', 
                                q_text, 
                                default_score
                            )
                            
                            # 2. 然后插入学生答案
                            scoring_details = json.dumps({
                                "correct_answer": correct_answer,
                                "is_correct": is_correct,
                                "max_score": default_score,
                                "ai_graded": True  # 标记为AI评分
                            })
                            
                            # AI评分反馈
                            if not student_answer:
                                ai_feedback = f"AI评判: 题目未匹配。未作答。正确答案应为: {correct_answer}，得分: 0/{default_score}"
                            else:
                                ai_feedback = f"AI评判: 题目未匹配。标准答案: {correct_answer}"
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
                                'true_false', 
                                student_answer, 
                                default_score if is_correct else 0,
                                ai_feedback,
                                scoring_details
                            )
                            print(f"AI阅卷结果已保存到数据库: 题目ID={new_question_id}, 学生ID={student_id}")
                            
                        except Exception as e:
                            import traceback
                            print(f"将AI阅卷结果保存到数据库时发生错误: {str(e)}")
                            print(traceback.format_exc())
                        
                is_correct_list.append(is_correct)
                
                print(f"AI评判结果：题目={q_text[:30]}..., 标准答案={correct_answer}, 学生答案={student_answer}, 得分={scores[-1]}")
        
        # 插入学生答案到数据库 - 新增部分
        if student_id:
            for i, (student_answer, correct_answer, score, is_correct, question_id, max_score) in enumerate(zip(student_answers, correct_answers, scores, is_correct_list, question_ids, max_scores)):
                if question_id:
                    # 查询该题目在questions表中的ID
                    q_id = get_question_id(conn, session_id, question_id, 'true_false_questions')
                    
                    if q_id:
                        # 生成评分详情JSON
                        scoring_details = json.dumps({
                            "correct_answer": correct_answer,
                            "is_correct": is_correct,
                            "max_score": max_score
                        })
                        
                        # AI评分反馈
                        ai_feedback = f"标准答案: {correct_answer}"
                        if is_correct:
                            ai_feedback += f"。答案正确，得分: {score}/{max_score}"
                        else:
                            ai_feedback += f"。答案错误，得分: 0/{max_score}"
                        
                        # 插入student_answers表
                        insert_student_answers_to_db(
                            conn, 
                            session_id, 
                            student_id, 
                            q_id, 
                            'true_false', 
                            student_answer, 
                            score if is_correct else 0,
                            ai_feedback,
                            scoring_details
                        )
                        print(f"已将学生答案保存到数据库: 题目ID={q_id}, 学生ID={student_id}")
                    else:
                        print(f"警告: 无法在questions表中找到对应题目: source_id={question_id}")
        
        conn.close()
        
        # 如果没有找到答案，提供默认值
        if not correct_answers:
            correct_answers = ["对", "错"]  # 根据题目内容的常识判断
        
        # 如果没有学生答案，可能是提取失败
        if not student_answers:
            # 尝试使用AI直接从文本中提取答案
            extract_prompt = f"""
    从以下判断题考试内容中提取学生的答案（对/错），以JSON格式返回。
    如果无法确定学生答案，请返回空字符串。

    考试内容:
    {Otxt}

    返回格式:
    {{
        "answers": ["对/错", "对/错"]
    }}
    """
            extract_response = new(extract_prompt, "")
            
            try:
                extract_data = json.loads(extract_response)
                student_answers = extract_data.get("answers", [])
            except:
                # 如果失败，假设学生未作答
                student_answers = [""] * len(correct_answers)
        
        # 返回结果
        print(f"学生答案：{student_answers}")
        print(f"正确答案：{correct_answers}")
        print(f"各题得分：{scores}")
        print(f"总得分：{total_score}")
        
        return student_answers, correct_answers, total_score
    
    except Exception as e:
        import traceback
        print(f"判断题评分过程中发生错误: {str(e)}")
        print(traceback.format_exc())
        return [], [], 0


if __name__ == '__main__':
    tf_grading("java", 1, 1)