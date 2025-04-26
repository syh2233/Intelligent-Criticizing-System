import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from split_and_ocr.ai import new
import re
import sqlite3
import json
from split_and_ocr.read.db_utils import insert_student_answers_to_db, get_question_id, get_db_connection, get_question_score, get_question_from_text, insert_question_to_db


def answer_readexit(subject, user_id, session_id):
    # 获取代码文件所在目录的路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 获取当前目录下所有txt文件
    files = [f for f in os.listdir(current_dir) if f.endswith('.txt')]
    # 匹配包含"简答"且文件名长度大于2的文件
    fill_files = [f for f in files if re.search(r'简答.+', f)]

    if not fill_files:
        raise FileNotFoundError("未找到包含'简答'的文件")
    with open(os.path.join(current_dir, fill_files[0]), "r", encoding="utf-8") as f:
        Otxt = f.read()
    
    # 使用JSON格式请求AI进行题目提取
    line1 = f"{Otxt}"
    line2 = """请将以下简答题进行整理并返回JSON格式数据。要求：
1. 整理原试卷中的简答题，不进行答案补充但要矫正和补充题目
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
                questions = []
                for item in response.split("----"):
                    try:
                        a, b = item.split("---")
                        questions.append(a.strip())
                    except:
                        if item.strip():
                            questions.append(item.strip())
        else:
            questions = []
            for item in response.split("----"):
                try:
                    a, b = item.split("---")
                    questions.append(a.strip())
                except:
                    if item.strip():
                        questions.append(item.strip())
    
    print(f"整理出的题目：{questions}")
    
    # 在循环外打开数据库连接
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'It_g.db')
    conn = sqlite3.connect(db_path)
    
    answers = []
    key_points_list = []
    for i, question in enumerate(questions):
        if not question.strip():
            continue
            
        # 使用JSON格式获取参考答案
        line_1 = f"{question}"
        line_2 = """分析以下简答题并以JSON格式返回参考答案和关键点：
{
    \"reference_answer\": \"详细完整的标准参考答案\",
    \"key_points\": \"考点关键词，用|分隔\"
}"""
        
        answer_response = new(line_1, line_2)
        
        try:
            # 解析JSON响应
            answer_data = json.loads(answer_response)
            reference_answer = answer_data.get("reference_answer", "")
            key_points = answer_data.get("key_points", "")
        except json.JSONDecodeError:
            # 如果无法解析为JSON，尝试提取文本中的JSON部分
            json_match = re.search(r'\{.*\}', answer_response, re.DOTALL)
            if json_match:
                try:
                    answer_data = json.loads(json_match.group())
                    reference_answer = answer_data.get("reference_answer", "")
                    key_points = answer_data.get("key_points", "")
                except:
                    # 兜底方案：再次单独请求
                    reference_answer = get_reference_answer(question)
                    key_points = get_key_points(question)
            else:
                # 兜底方案：再次单独请求
                reference_answer = get_reference_answer(question)
                key_points = get_key_points(question)
        
        answers.append(reference_answer)
        key_points_list.append(key_points)
        
        # 使用当前连接插入数据库
        question_id = insert_into_db_with_conn(conn, subject, question, reference_answer, key_points, user_id)
        
        # 如果提供了session_id，则插入questions表
        if session_id:
            question_order = i + 1
            insert_into_questions_with_conn(conn, session_id, question, 10, question_order, question_id)
    
    # 关闭数据库连接
    conn.close()
    
    print(f"参考答案列表：{answers}")
    print(f"关键点列表：{key_points_list}")
    return answers, key_points_list


def get_reference_answer(question):
    """获取简答题参考答案"""
    line_1 = f"{question}"
    line_2 = "是试卷简答题题目，请给出标准参考答案，要求详细完整"
    return new(line_1, line_2)


def get_key_points(question):
    """获取简答题关键点"""
    line_1 = f"{question}"
    line_2 = "是试卷简答题题目，请给出考点关键词用|分隔开，要求只输出关键词"
    return new(line_1, line_2)


def insert_into_db_with_conn(conn, subject, question_text, reference_answer, key_points, user_id):
    """插入简答题到short_answer_questions表并返回插入的ID"""
    cursor = conn.cursor()
    
    # 插入数据
    cursor.execute('''
        INSERT INTO short_answer_questions 
        (subject, question_text, reference_answer, key_points, score, difficulty, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    ''', (subject, question_text, reference_answer, key_points, 10, 3, user_id))
    
    # 获取插入的ID
    question_id = cursor.lastrowid
    conn.commit()
    
    return question_id


def insert_into_questions_with_conn(conn, session_id, question_text, score, question_order, source_question_id):
    """
    将简答题插入到questions表
    
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
        VALUES (?, 'short_answer', ?, ?, ?, ?, 'short_answer_questions')
    ''', (session_id, question_text, score, question_order, source_question_id))
    
    conn.commit()
    return cursor.lastrowid


def answer_grading(subject, session_id, student_id):
    """
    从简答题txt文件中提取学生答案，并与数据库中的参考答案进行比较
    返回：(学生答案列表, 参考答案列表, 总得分)
    """
    try:
        # 获取代码文件所在目录的路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 获取当前目录下所有txt文件
        files = [f for f in os.listdir(current_dir) if f.endswith('.txt')]
        # 匹配包含"简答"且文件名长度大于2的文件
        answer_files = [f for f in files if re.search(r'简答.+', f)]

        if not answer_files:
            raise FileNotFoundError("未找到包含'简答'的文件")
        
        with open(os.path.join(current_dir, answer_files[0]), "r", encoding="utf-8") as f:
            txt_content = f.read()
        
        # 改进从文本中分割题目和学生答案的逻辑
        # 使用题号模式识别多个题目
        student_answers = []
        questions = []
        
        # 使用AI提取简答题题目和答案
        ai_prompt = f"""
请从以下文本中提取简答题的题号、完整题目和学生答案，尤其注意区分完整题目和学生回答。返回JSON格式。

文本内容:
{txt_content}

注意事项：
1. 请仔细区分题目和学生的回答。题目通常以题号开始，学生答案通常从新的一行开始。
2. 题目可能分多行，可能包含"简述"、"论述"、"描述"等指示词。
3. 特别注意像"简述Java中的public、private和protected访问修饰符的作用和区别"这样的题目，后面的"访问修饰符的作用和区别"是题目的一部分，不是学生回答。
4. 特别注意像"解释Java中的try-catch块的作用"这样的题目，后面的"块的作用"是题目的一部分，不是学生回答。
5. 若某题没有看到明确学生回答，则将学生答案设为空字符串。
6. 确保题号的一致性，如题目以"题目10"或"10."开头。

请返回以下格式的JSON:
{{
    "questions": [
        {{
            "question_number": "10",
            "question_text": "完整的题目文本，包括所有说明和要求",
            "student_answer": "学生的回答，可能为空"
        }},
        {{
            "question_number": "11",
            "question_text": "完整的题目文本...",
            "student_answer": ""
        }}
    ]
}}
"""
        
        print("调用AI提取简答题...")
        ai_response = new("你是一个专业的文本分析助手，请提取文本中的简答题和答案，准确区分题干和答案", ai_prompt)
        
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
            print(f"AI成功提取了{len(extracted_questions)}道简答题")
            
            # 处理AI提取的题目和答案
            for q in extracted_questions:
                question_number = q.get("question_number", "")
                question_text = q.get("question_text", "")
                student_answer = q.get("student_answer", "")
                
                # 格式化题目文本，确保题号一致性
                full_question = f"题目{question_number}：{question_text}" if not question_text.startswith(f"题目{question_number}") else question_text
                
                questions.append(full_question)
                student_answers.append(student_answer)
                
                print(f"题目 {question_number}: {question_text[:50]}...")
                print(f"答案: {student_answer[:50]}..." if student_answer else "答案: 无答案")
                
        except Exception as e:
            print(f"解析AI响应失败: {str(e)}")
            print("回退到基本分割方法...")
            
            # 如果AI提取失败，回退到基于题号的分割方法
            question_pattern = r'(?:\d+[、.．]|题目\s*\d+[:：]?)\s*'
            sections = re.split(question_pattern, txt_content)
            
            # 如果分割成功（至少2段），第一段可能是空的或标题，之后每段是题目+答案
            if len(sections) > 1:
                # 去除第一个可能为空的段落
                sections = [s for s in sections if s.strip()]
                print(f"通过题号分割，找到 {len(sections)} 个题目")
                
                # 提取题号
                title_matches = re.findall(question_pattern, txt_content)
                
                for i, section in enumerate(sections):
                    # 取题号
                    question_number = "未知" if i >= len(title_matches) else re.sub(r'[^0-9]', '', title_matches[i])
                    
                    # 分割题目和答案
                    parts = re.split(r'\n\s*(?=[\u4e00-\u9fa5])', section, 1)
                    if len(parts) > 1:
                        question_text = parts[0].strip()
                        student_answer = parts[1].strip()
                    else:
                        question_text = section.strip()
                        student_answer = ""
                    
                    questions.append(f"题目{question_number}：{question_text}")
                    student_answers.append(student_answer)
            else:
                # 如果无法通过题号分割，使用简单方法
                print("使用简单分割方法")
                lines = txt_content.split('\n')
                
                # 默认第一行是题目
                question_text = lines[0] if lines else ""
                questions.append(question_text)
                
                # 剩余所有行视为答案
                student_answer = "\n".join([l for l in lines[1:] if l.strip()])
                student_answers.append(student_answer)
        
        # 确保至少有一道题目
        if not student_answers:
            student_answers = ["未提供答案"]
            
        if not questions:
            questions = ["未识别到题目"]
        
        # 使用新的数据库连接方法
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取所有简答题
        cursor.execute('''
            SELECT id, question_text, reference_answer, key_points, score FROM short_answer_questions 
            WHERE subject = ?
        ''', (subject,))
        
        db_questions = cursor.fetchall()
        
        # 准备返回值
        reference_answers = []
        total_score = 0
        question_ids = []
        scores = []
        max_scores = []
        
        # 对每个题目和学生答案进行评分
        for q_index, (question_text, student_answer) in enumerate(zip(questions, student_answers)):
            print(f"\n处理题目 {q_index + 1}: {question_text[:30]}...")
            
            # 找到匹配的题目
            best_match = None
            highest_similarity = 0
            
            for db_q in db_questions:
                q_id, db_q_text, q_ref_answer, q_key_points, q_score = db_q
                
                # 计算题目相似度 (简单计算关键词重合率)
                q_words = set(re.findall(r'\b\w+\b', db_q_text.lower()))
                
                if "main" in db_q_text.lower() and "java" in db_q_text.lower() and "main" in question_text.lower():
                    # 如果题目包含"main"和"java"，认为是匹配的
                    similarity = 0.9
                else:
                    # 计算词汇相似度
                    title_words = set(re.findall(r'\b\w+\b', question_text.lower()))
                    if q_words and title_words:
                        common_words = q_words.intersection(title_words)
                        similarity = len(common_words) / len(q_words)
                        print(f"题目相似度: {similarity:.2f}, 共同关键词: {len(common_words)}, DB题目关键词: {len(q_words)}")
                    else:
                        similarity = 0
                
                if similarity > highest_similarity:
                    highest_similarity = similarity
                    best_match = db_q
            
            # 如果找到匹配的题目
            if best_match and highest_similarity > 0.3:
                q_id, db_q_text, q_ref_answer, q_key_points, source_score = best_match
                reference_answers.append(q_ref_answer)
                question_ids.append(q_id)
                
                # 从questions表获取该题的分数
                question_score = get_question_score(conn, session_id, q_id, 'short_answer_questions')
                
                if question_score is not None:
                    print(f"从questions表获取到分数: {question_score} (源题ID: {q_id})")
                    max_score = question_score
                else:
                    # 如果在questions表中找不到该题，尝试通过题目文本匹配
                    q_id, q_score = get_question_from_text(conn, session_id, db_q_text, 'short_answer')
                    if q_id and q_score:
                        max_score = q_score
                        print(f"通过文本匹配在questions表中找到题目: ID={q_id}, 分数={q_score}")
                    else:
                        # 如果找不到，使用源表中的分数
                        max_score = source_score
                        print(f"使用源表分数: {source_score} (未在questions表中找到匹配题目)")
                
                max_scores.append(max_score)
                
                # 处理空答案情况
                if not student_answer or student_answer.strip() == "":
                    print(f"学生未作答，得分: 0/{max_score}")
                    scores.append(0)
                    ai_feedback = f"未作答。参考答案: {q_ref_answer[:50]}..., 得分: 0/{max_score}"
                    continue
                
                # 直接比较文本相似度
                # 移除所有空白字符和标点符号后比较
                clean_ref = re.sub(r'[\s\n\r\t.,;:!?，。；：！？]', '', q_ref_answer)
                clean_student = re.sub(r'[\s\n\r\t.,;:!?，。；：！？]', '', student_answer)

                # 计算文本相似度
                if clean_ref and clean_student:
                    # 如果两者完全相同，直接满分
                    if clean_ref == clean_student:
                        print(f"答案完全相同，直接给满分 {max_score}")
                        earned_score = max_score
                        total_score += earned_score
                        scores.append(earned_score)
                        
                        # 保存AI评分结果，供后续插入数据库
                        ai_feedback = f"答案与参考答案完全匹配，得分: {earned_score}/{max_score}"
                        continue
                    
                    # 计算文本相似度
                    from difflib import SequenceMatcher
                    similarity_ratio = SequenceMatcher(None, clean_ref, clean_student).ratio()
                    print(f"答案相似度: {similarity_ratio:.2f}")
                    
                    # 如果相似度很高，给予高分
                    if similarity_ratio > 0.95:
                        earned_score = max_score
                        total_score += earned_score
                        scores.append(earned_score)
                        print(f"答案高度相似，得分: {earned_score}/{max_score}")
                        ai_feedback = f"答案与参考答案高度相似，得分: {earned_score}/{max_score}"
                        continue
                    elif similarity_ratio > 0.8:
                        earned_score = int(max_score * 0.9)
                        total_score += earned_score
                        scores.append(earned_score)
                        print(f"答案相当相似，得分: {earned_score}/{max_score}")
                        ai_feedback = f"答案与参考答案相当相似，得分: {earned_score}/{max_score}"
                        continue
                
                # 使用AI评分
                prompt = f"""
请评估以下简答题的学生回答：

参考答案: {q_ref_answer}
学生回答: {student_answer}

请检查学生回答是否包含所有关键点并评分，返回0-{max_score}分之间的整数评分。
同时提供简短的评语。
"""
                score_result = new(prompt, "")
                
                # 提取分数
                score_match = re.search(r'(\d+)', score_result)
                if score_match:
                    earned_score = int(score_match.group(1))
                    # 确保在0-max_score范围内
                    earned_score = max(0, min(max_score, earned_score))
                    total_score += earned_score
                    scores.append(earned_score)
                else:
                    # 默认分数为一半
                    earned_score = max_score // 2
                    total_score += earned_score
                    scores.append(earned_score)
                
                # 保存AI评分结果，供后续插入数据库
                ai_feedback = score_result
                
                # 如果AI给出的分数过低但内容高度相似，则覆盖AI的判断
                if earned_score < max_score * 0.7:
                    from difflib import SequenceMatcher
                    similarity = SequenceMatcher(None, q_ref_answer, student_answer).ratio()
                    if similarity > 0.8:
                        new_score = int(max_score * 0.9)
                        total_score = total_score - earned_score + new_score
                        scores[-1] = new_score
                        print(f"AI评分过低但内容相似，调整分数为: {new_score}")
                        ai_feedback = f"答案与参考答案相似度高，调整得分: {new_score}/{max_score}"
            else:
                # 如果没有找到匹配题目，使用AI直接评分
                reference_answers.append("未找到匹配题目，使用AI直接评分")
                question_ids.append(None)
                
                # 使用默认最大分数
                default_max_score = 10
                max_scores.append(default_max_score)
                
                # 直接评估 - 优化为更通用的AI阅卷功能
                direct_prompt = f"""
请评估以下简答题的学生回答：

题目: {question_text}
学生回答: 
{student_answer}

请分析题目要求和学生答案，考虑以下方面：
1. 学生答案是否回答了题目的核心问题
2. 答案的完整性和准确性
3. 关键概念的覆盖程度
4. 论述的逻辑性和条理性

请给出0-{default_max_score}分之间的整数评分，并简要说明评分理由。
"""
                score_result = new("你是一名经验丰富的教师，正在评判简答题", direct_prompt)
                
                # 提取分数
                score_match = re.search(r'(\d+)', score_result)
                if score_match:
                    earned_score = int(score_match.group(1))
                    # 确保在0-default_max_score范围内
                    earned_score = max(0, min(default_max_score, earned_score))
                    total_score += earned_score
                    scores.append(earned_score)
                else:
                    # 默认分数
                    earned_score = default_max_score // 2
                    scores.append(earned_score)
                    total_score += earned_score
                
                # 同时生成参考答案
                ref_prompt = f"""
请为以下简答题提供一个标准参考答案：

{question_text}

请提供一个全面、准确、符合教学标准的答案。
"""
                ref_answer = new("你是一名专业教师，正在提供参考答案", ref_prompt)
                reference_answers[-1] = ref_answer  # 更新参考答案
                
                # 保存AI评分结果，供后续插入数据库
                ai_feedback = score_result
                
                # 如果提供了session_id和student_id，插入数据库 - 新增
                if session_id and student_id:
                    try:
                        # 1. 首先在questions表中创建新题目
                        new_question_id = insert_question_to_db(
                            conn, 
                            session_id, 
                            'short_answer', 
                            question_text,  # 题目文本
                            default_max_score
                        )
                        
                        # 2. 然后插入学生答案
                        scoring_details = json.dumps({
                            "reference_answer": ref_answer,
                            "score": earned_score,
                            "max_score": default_max_score,
                            "ai_graded": True  # 标记为AI评分
                        })
                        
                        # 插入student_answers表
                        insert_student_answers_to_db(
                            conn, 
                            session_id, 
                            student_id, 
                            new_question_id, 
                            'short_answer', 
                            student_answer, 
                            earned_score,
                            f"AI评判: 题目未匹配。{ai_feedback}",
                            scoring_details
                        )
                        print(f"AI阅卷结果已保存到数据库: 题目ID={new_question_id}, 学生ID={student_id}, 分数={earned_score}/{default_max_score}")
                        
                    except Exception as e:
                        import traceback
                        print(f"将AI阅卷结果保存到数据库时发生错误: {str(e)}")
                        print(traceback.format_exc())
        
        # 插入学生答案到数据库 - 新增部分
        if student_id:
            for i, (question_text, student_answer, reference_answer, question_id, earned_score, max_score) in enumerate(zip(
                    questions, student_answers, reference_answers, question_ids, scores, max_scores)):
                if question_id:
                    # 查询该题目在questions表中的ID
                    q_id = get_question_id(conn, session_id, question_id, 'short_answer_questions')
                    
                    if q_id:
                        # 生成评分详情JSON
                        scoring_details = json.dumps({
                            "reference_answer": reference_answer,
                            "score": earned_score,
                            "max_score": max_score
                        })
                        
                        # 提取AI反馈的关键信息（去除分数）
                        ai_feedback_text = re.sub(r'\d+分', '', locals().get('ai_feedback', ''))
                        ai_feedback_text = re.sub(r'分数[:：]?\s*\d+', '', ai_feedback_text)
                        ai_feedback_text = f"得分: {earned_score}/{max_score}. " + ai_feedback_text.strip()
                        
                        # 插入student_answers表
                        insert_student_answers_to_db(
                            conn, 
                            session_id, 
                            student_id, 
                            q_id, 
                            'short_answer', 
                            student_answer, 
                            earned_score,
                            ai_feedback_text,
                            scoring_details
                        )
                        print(f"已将学生答案保存到数据库: 题目ID={q_id}, 学生ID={student_id}")
                    else:
                        print(f"警告: 无法在questions表中找到对应题目: source_id={question_id}")
        
        conn.close()
        
        # 确保返回内容完整
        if not student_answers:
            student_answers = ["未提供答案"]
        if not reference_answers:
            reference_answers = ["未找到参考答案"]
        
        print(f"\n简答题评分总结:")
        print(f"题目数量: {len(questions)}")
        print(f"学生答案数量: {len(student_answers)}")
        print(f"参考答案数量: {len(reference_answers)}")
        print(f"总得分: {total_score}")
        
        for i, (q, sa, ra, s, ms) in enumerate(zip(
                questions, student_answers, reference_answers, 
                scores, max_scores)):
            print(f"\n题目 {i+1}: {q[:30]}...")
            print(f"学生答案: {sa[:30]}..." if sa else "学生答案: 未作答")
            print(f"得分: {s}/{ms}")
        
        return student_answers, reference_answers, total_score
    
    except Exception as e:
        import traceback
        print(f"简答题评分过程中发生错误: {str(e)}")
        print(traceback.format_exc())
        return ["错误"], ["评分过程出错"], 0


if __name__ == '__main__':
    answer_grading("java", 1, 1)