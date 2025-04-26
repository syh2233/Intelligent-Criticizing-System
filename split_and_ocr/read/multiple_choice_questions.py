import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from split_and_ocr.ai import new
import re
import sqlite3
import json
from split_and_ocr.read.db_utils import insert_student_answers_to_db, get_question_id, get_db_connection, get_question_score, get_question_from_text, insert_question_to_db

def choice_readexit(subject, user_id, session_id):
    # 获取代码文件所在目录的路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 获取当前目录下所有txt文件
    files = [f for f in os.listdir(current_dir) if f.endswith('.txt')]
    # 匹配包含"选择"且文件名长度大于2的文件
    fill_files = [f for f in files if re.search(r'选择.+', f)]

    if not fill_files:
        raise FileNotFoundError("未找到包含'选择'的文件")
    
    with open(os.path.join(current_dir, fill_files[0]), "r", encoding="utf-8") as f:
        Otxt = f.read()
    
    # 使用JSON格式请求AI进行题目提取
    line1 = f"{Otxt}"
    line2 = """请将以下选择题进行整理并返回JSON格式数据。要求：
1. 整理原试卷中的选择题，将括号统一为中文括号（）
2. 仅返回题目及选项，去除识别到的其他类型题目
3. 返回格式为JSON：
{
    \"questions\": [
        {
            \"question\": \"题目文本（）\",
            \"options\": [\"A. 选项A\", \"B. 选项B\", \"C. 选项C\", \"D. 选项D\"]
        },
        {
            \"question\": \"题目文本（）\", 
            \"options\": [\"A. 选项A\", \"B. 选项B\", \"C. 选项C\", \"D. 选项D\"]
        }
    ]
}"""

    response = new(line1, line2)
    
    try:
        # 解析JSON响应
        questions_data = json.loads(response)
        questions_list = questions_data.get("questions", [])
    except json.JSONDecodeError:
        # 如果无法解析为JSON，尝试提取文本中的JSON部分
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                questions_data = json.loads(json_match.group())
                questions_list = questions_data.get("questions", [])
            except:
                # 兜底方案：使用原方法分割
                questions_list = []
                for item in response.split("---"):
                    if len(item.strip()) > 5:  # 确保文本有足够长度
                        questions_list.append({"question": item, "options": []})
        else:
            questions_list = []
            for item in response.split("---"):
                if len(item.strip()) > 5:
                    questions_list.append({"question": item, "options": []})
    
    print(f"整理出的题目数量：{len(questions_list)}")
    
    # 在循环外打开数据库连接
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'It_g.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    answers = []
    for i, question_data in enumerate(questions_list):
        question_text = question_data.get("question", "")
        options = question_data.get("options", [])
        
        # 提取选项
        option_a = options[0] if len(options) > 0 else ""
        option_b = options[1] if len(options) > 1 else ""
        option_c = options[2] if len(options) > 2 else ""
        option_d = options[3] if len(options) > 3 else ""
        
        # 使用JSON格式获取答案
        line_1 = f"问题：{question_text}\n选项：{' '.join(options)}"
        line_2 = """分析以下选择题并以JSON格式返回答案和解析：
{
    \"answer\": \"选择题的正确答案（A、B、C或D）\",
    \"explanation\": \"解析说明正确答案的原因\"
}"""
        
        answer_response = new(line_1, line_2)
        
        try:
            # 解析JSON响应
            answer_data = json.loads(answer_response)
            answer = answer_data.get("answer", "").strip().upper()
            if not answer or answer not in ["A", "B", "C", "D"]:
                # 如果答案不是有效选项，尝试从首字母提取
                answer = answer[0] if answer and answer[0] in ["A", "B", "C", "D"] else "A"
            explanation = answer_data.get("explanation", "")
        except json.JSONDecodeError:
            # 如果无法解析为JSON，尝试提取文本中的JSON部分
            json_match = re.search(r'\{.*\}', answer_response, re.DOTALL)
            if json_match:
                try:
                    answer_data = json.loads(json_match.group())
                    answer = answer_data.get("answer", "").strip().upper()
                    if not answer or answer not in ["A", "B", "C", "D"]:
                        answer = answer[0] if answer and answer[0] in ["A", "B", "C", "D"] else "A"
                    explanation = answer_data.get("explanation", "")
                except:
                    # 兜底方案
                    answer = "A"  # 默认答案
                    explanation = ""
            else:
                # 查找答案模式 "答案: A" 或类似形式
                answer_match = re.search(r'答案[：:]\s*([A-D])', answer_response)
                answer = answer_match.group(1) if answer_match else "A"
                explanation = ""
        
        answers.append(answer)
        
        # 插入数据库
        question_id = insert_into_db_with_conn(conn, subject, question_text, option_a, option_b, option_c, option_d, answer, explanation, user_id)
        
        # 如果提供了session_id，则插入questions表
        if session_id:
            question_order = i + 1
            insert_into_questions_with_conn(conn, session_id, question_text, 5, question_order, question_id)
    
    # 关闭数据库连接
    conn.close()
    
    print(f"答案列表：{answers}")
    return answers


def insert_into_db_with_conn(conn, subject, question_text, option_a, option_b, option_c, option_d, correct_answer, explanation, user_id):
    cursor = conn.cursor()
    
    # 插入数据
    cursor.execute('''
        INSERT INTO multiple_choice_questions 
        (subject, question_text, option_a, option_b, option_c, option_d, 
         correct_answer, explanation, score, difficulty, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    ''', (subject, question_text, option_a, option_b, option_c, option_d, correct_answer, explanation, 5, 3, user_id))
    
    # 获取插入的ID
    question_id = cursor.lastrowid
    conn.commit()
    
    return question_id


def insert_into_questions_with_conn(conn, session_id, question_text, score, question_order, source_question_id):
    """
    将选择题插入到questions表
    
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
        VALUES (?, 'multiple_choice', ?, ?, ?, ?, 'multiple_choice_questions')
    ''', (session_id, question_text, score, question_order, source_question_id))
    
    conn.commit()
    return cursor.lastrowid


def clean_text(text):
    """清理文本，移除标点和特殊字符，转为小写"""
    return re.sub(r'[()（）.，、；：]', '', text).lower()


def choice_grading(subject, session_id, student_id):
    """
    从选择题txt文件中提取学生答案，并与数据库中的正确答案进行比较
    返回：(总得分, 学生答案列表, 正确答案列表, 题目分数列表)
    """
    try:
        # 获取代码文件所在目录的路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 获取当前目录下所有txt文件
        files = [f for f in os.listdir(current_dir) if f.endswith('.txt')]
        # 修改匹配模式，同时匹配"选择"和"一"开头的文件
        choice_files = [f for f in files if re.search(r'一\.选择|选择|^一[\.．]', f)]
        
        # 如果没找到，列出所有txt文件以便调试
        if not choice_files:
            print("当前目录下的所有txt文件:")
            for f in files:
                print(f"- {f}")
            raise FileNotFoundError("未找到选择题文件，请检查文件名")
        
        choice_file = choice_files[0]
        print(f"找到选择题文件: {choice_file}")
        
        with open(os.path.join(current_dir, choice_file), "r", encoding="utf-8") as f:
            Otxt = f.read()
        
        print(f"文件内容前100个字符: {Otxt[:100]}")
        
        # 使用AI进行选择题提取
        ai_prompt = f"""
请从以下文本中提取选择题的题号和题目文本，并检查是否有学生填写的答案，返回JSON格式。

文本内容:
{Otxt}

注意事项：
1. 仔细分析每道题，判断学生是否真的在题目中圈选或填写了答案
2. 只有在明确看到括号()或其他明确标记中填写了选项(A/B/C/D)时，才认为有学生答案
3. 若题目中没有明确的学生答案标记，请将student_answer设为空字符串""
4. 不要把题目描述或选项中出现的字母误认为是学生答案

请返回以下格式的JSON:
{{
    "questions": [
        {{
            "question_number": "1",
            "question_text": "题目文本...",
            "student_answer": ""  // 除非明确看到学生圈选了答案，否则应为空
        }},
        {{
            "question_number": "2",
            "question_text": "题目文本...",
            "student_answer": ""
        }}
    ]
}}
"""
        
        print("调用AI提取选择题...")
        ai_response = new("你是一个专业的文本分析助手，请提取文本中的选择题和答案。", ai_prompt)
        
        # 尝试解析AI响应
        try:
            # 提取JSON部分
            json_match = re.search(r'(\{.*\})', ai_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                data = json.loads(json_str)
            else:
                data = json.loads(ai_response)
            
            questions = data.get("questions", [])
            print(f"AI成功提取了{len(questions)}道选择题")
            
        except Exception as e:
            print(f"解析AI响应失败: {str(e)}")
            questions = []
        
        # 使用新的数据库连接方法
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 先获取所有选择题，按科目过滤
        cursor.execute('SELECT id, question_text, correct_answer, score FROM multiple_choice_questions WHERE subject = ?', (subject,))
        all_db_questions = cursor.fetchall()
        print(f"从数据库获取到 {len(all_db_questions)} 道 {subject} 科目的选择题")
        
        # 初始化结果变量
        student_answers = []  # 学生答案列表
        correct_answers = []  # 正确答案列表
        question_ids = []     # 题目ID列表
        scores = []           # 每题分数列表
        is_correct_list = []  # 是否答对列表
        total_score = 0       # 总分
        
        # 跟踪已处理的题目
        processed_questions = set()
        saved_answers = set()  # 用于跟踪已保存到数据库的题目
        
        # 处理每道题
        for q in questions:
            question_number = q.get("question_number", "")
            question_text = q.get("question_text", "")
            student_answer = q.get("student_answer", "").strip().upper()
            
            # 生成唯一标识
            question_key = f"{question_number}_{question_text[:30]}"
            
            # 如果该题目已处理过，跳过
            if question_key in processed_questions:
                print(f"题目 {question_number} 已处理过，跳过")
                continue
            
            processed_questions.add(question_key)
            student_answers.append(student_answer)
            
            # 查找最佳匹配
            best_match = None
            highest_match_score = 0
            
            print(f"正在匹配题目 {question_number}: {question_text[:30]}...")
            
            # 清理文本进行匹配
            clean_q_text = clean_text(question_text)
            
            for db_q in all_db_questions:
                db_id, db_text, db_answer, source_score = db_q
                clean_db_text = clean_text(db_text)
                
                match_score = 0
                
                # 首先尝试前缀或者关键词匹配
                if clean_q_text[:10] and clean_db_text[:10] and clean_q_text[:10] == clean_db_text[:10]:
                    match_score = 0.6
                    if len(clean_q_text) > 20 and len(clean_db_text) > 20 and clean_q_text[:20] == clean_db_text[:20]:
                        match_score = 0.8  # 如果前20个字符也匹配，提高分数
                
                # 特殊处理Java应用程序相关题目
                if "java应用程序" in clean_q_text and "java应用程序" in clean_db_text:
                    if "独立运行" in clean_q_text and "独立运行" in clean_db_text:
                        match_score = 0.9
                        print(f"特殊匹配成功: Java应用程序相关题目")
                
                # 如果前缀匹配未成功，仍进行整体相似度计算
                if match_score == 0:  
                    # 简单的文本包含检查
                    words_q = set(clean_q_text.split())
                    words_db = set(clean_db_text.split())
                    common_words = words_q.intersection(words_db)
                    
                    if len(words_q) > 0:
                        match_score = len(common_words) / len(words_q)
            
                if match_score > highest_match_score:
                    highest_match_score = match_score
                    best_match = db_q
            
            # 处理匹配结果
            matched_question_id = None
            is_ai_graded = False
            
            if best_match and highest_match_score > 0.2:  # 降低阈值从0.3到0.2
                db_id, db_text, correct_answer, source_score = best_match
                matched_question_id = db_id
                print(f"题目 {question_number} 匹配成功，匹配分数: {highest_match_score:.2f}")
                
                # 从questions表获取该题的分数
                question_score = get_question_score(conn, session_id, db_id, 'multiple_choice_questions')
                
                if question_score is not None:
                    print(f"从questions表获取到分数: {question_score} (源题ID: {db_id})")
                    score = question_score
                else:
                    # 如果在questions表中找不到该题，尝试通过题目文本匹配
                    q_id, q_score = get_question_from_text(conn, session_id, question_text, 'multiple_choice')
                    if q_id and q_score:
                        score = q_score
                        print(f"通过文本匹配在questions表中找到题目: ID={q_id}, 分数={q_score}")
                    else:
                        # 如果找不到，使用源表中的分数
                        score = source_score
                        print(f"使用源表分数: {source_score}")
            else:
                # 使用AI评分
                print(f"题目 {question_number} 没有找到匹配，使用AI评分")
                is_ai_graded = True
                default_score = 5  # 默认选择题分数
                
                # 构建评估提示
                ai_prompt = f"""
请判断以下选择题的正确答案，并评估学生答案是否正确：

题目：{question_text}
学生答案：{student_answer}

1. 请首先根据题目内容判断正确选项是哪个(A/B/C/D)
2. 然后判断学生答案是否正确
3. 只返回正确选项和学生是否正确，格式为：
   正确答案：A/B/C/D
   学生答案：正确/错误
"""
                
                ai_response = new("你是一名专业教师，正在评判选择题", ai_prompt)
                
                # 提取AI判断的正确答案
                correct_answer_match = re.search(r'正确答案[：:]\s*([A-D])', ai_response)
                if correct_answer_match:
                    correct_answer = correct_answer_match.group(1)
                else:
                    # 尝试直接提取A/B/C/D
                    answer_match = re.search(r'[：:]\s*([A-D])', ai_response)
                    correct_answer = answer_match.group(1) if answer_match else "A"  # 默认A
                
                score = default_score
            
            # 评分逻辑
            is_correct = False
            if not student_answer:
                print(f"题目 {question_number} 学生未作答")
                is_correct = False
            else:
                is_correct = student_answer == correct_answer.strip().upper()
                
                if is_correct:
                    total_score += score
                    print(f"题目 {question_number} 答案正确! 得分: {score}")
                else:
                    print(f"题目 {question_number} 答案错误。学生答案: {student_answer}, 正确答案: {correct_answer}")
            
            # 更新结果列表
            correct_answers.append(correct_answer)
            scores.append(score if is_correct else 0)
            question_ids.append(matched_question_id)
            is_correct_list.append(is_correct)
            
            # 准备数据库插入
            if session_id and student_id:
                # 生成唯一标识
                answer_key = f"{session_id}_{student_id}_{question_text[:30]}"
                
                # 检查是否已经保存过
                if answer_key in saved_answers:
                    print(f"题目 {question_number} 答案已保存过，跳过")
                    continue
                
                saved_answers.add(answer_key)
                
                try:
                    # 如果是AI评分且没有匹配到题目，创建新题目
                    if is_ai_graded and not matched_question_id:
                        # 在questions表中创建新题目
                        new_question_id = insert_question_to_db(
                            conn, 
                            session_id, 
                            'multiple_choice', 
                            question_text, 
                            score
                        )
                        
                        # 更新matched_question_id为新创建的题目ID
                        matched_question_id = new_question_id
                    else:
                        # 如果匹配到了题目，查询该题目在questions表中的ID
                        q_id = get_question_id(conn, session_id, matched_question_id, 'multiple_choice_questions')
                        if q_id:
                            matched_question_id = q_id
                    
                    # 准备评分详情
                    scoring_details = json.dumps({
                        "correct_answer": correct_answer,
                        "is_correct": is_correct,
                        "max_score": score,
                        "ai_graded": is_ai_graded,
                        "answered": bool(student_answer)
                    })
                    
                    # AI评分反馈
                    if not student_answer:
                        ai_feedback = f"未作答。正确答案应为: {correct_answer}，得分: 0/{score}"
                    else:
                        if is_ai_graded:
                            ai_feedback = f"AI评判: "
                        else:
                            ai_feedback = ""
                            
                        ai_feedback += f"标准答案: {correct_answer}"
                        if is_correct:
                            ai_feedback += f"。答案正确，得分: {score}/{score}"
                        else:
                            ai_feedback += f"。答案错误，得分: 0/{score}"
                    
                    # 插入student_answers表
                    insert_student_answers_to_db(
                        conn, 
                        session_id, 
                        student_id, 
                        matched_question_id, 
                        'multiple_choice', 
                        student_answer, 
                        score if is_correct else 0,
                        ai_feedback,
                        scoring_details
                    )
                    print(f"AI阅卷结果已保存到数据库: 题目ID={matched_question_id}, 学生ID={student_id}")
                    
                except Exception as e:
                    import traceback
                    print(f"将阅卷结果保存到数据库时发生错误: {str(e)}")
                    print(traceback.format_exc())
        
        print(f"成功保存 {len(saved_answers)}/{len(questions)} 道题的学生答案")
        conn.close()
        
        return total_score, student_answers, correct_answers, scores
        
    except Exception as e:
        import traceback
        print(f"选择题评分过程中出错: {str(e)}")
        print(traceback.format_exc())
        return 0, [], [], []


if __name__ == "__main__":
    # choice_grading函数测试
    total_score, student_answers, correct_answers, question_scores = choice_grading("java", 1, 3)
    print(f"学生答案：{student_answers}")
    print(f"正确答案：{correct_answers}")
    print(f"题目分数：{question_scores}")
    print(f"总得分：{total_score}")