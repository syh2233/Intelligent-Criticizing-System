import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from split_and_ocr.ai import new
import re
import sqlite3
import json
from split_and_ocr.read.db_utils import insert_student_answers_to_db, get_question_id, get_db_connection, get_question_score, get_question_from_text, insert_question_to_db

def pro_readexit(subject, user_id, session_id=None):
    # 获取代码文件所在目录的路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 获取当前目录下所有txt文件
    files = [f for f in os.listdir(current_dir) if f.endswith('.txt')]
    # 匹配包含"编程"且文件名长度大于2的文件
    fill_files = [f for f in files if re.search(r'编程.+', f)]

    if not fill_files:
        raise FileNotFoundError("未找到包含'编程'的文件")
    with open(os.path.join(current_dir, fill_files[0]), "r", encoding="utf-8") as f:
        Otxt = f.read()
    
    # 使用JSON格式请求AI进行题目提取
    line1 = f"{Otxt}"
    line2 = """请将以下编程题进行整理并返回JSON格式数据。要求：
1. 整理原试卷中的编程题，不进行答案补充但要矫正和补充题目
2. 仅返回题目，去除识别到的其他类型题目
3. 从题目中提取出示例输入和示例输出，只保留输入数据本身，不要包含描述文字
4. 返回格式为JSON，格式如下：
{
    \"questions\": [
        {
            \"question_text\": \"编程题题目描述\", 
            \"sample_input\": \"1234\",
            \"sample_output\": \"10\"
        }
    ]
}
5. 记住不要返回任何解释文字，只返回JSON格式数据，而且\"sample_input\"和\"sample_output\"后面一定要有数据
"""

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
                for item in response.split("----"):
                    if len(item.strip()) > 5:  # 确保文本有足够长度
                        try:
                            q, a = item.split("---")
                            questions_list.append({"question_text": q.strip(), "sample_input": "", "sample_output": ""})
                        except:
                            questions_list.append({"question_text": item.strip(), "sample_input": "", "sample_output": ""})
        else:
            questions_list = []
            for item in response.split("----"):
                if len(item.strip()) > 5:
                    try:
                        q, a = item.split("---")
                        questions_list.append({"question_text": q.strip(), "sample_input": "", "sample_output": ""})
                    except:
                        questions_list.append({"question_text": item.strip(), "sample_input": "", "sample_output": ""})
    
    print(f"整理出的题目数量：{len(questions_list)}")
    
    # 在循环外打开数据库连接
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database', 'It_g.db')
    conn = sqlite3.connect(db_path)
    
    solutions = []
    answers = []
    for i, question_data in enumerate(questions_list):
        question_text = question_data.get("question_text", "")
        sample_input = question_data.get("sample_input", "")
        sample_output = question_data.get("sample_output", "")
        
        # 将问题文本与样例输入输出结合
        full_question = question_text
        if sample_input:
            full_question += f"\n示例输入:\n{sample_input}"
        if sample_output:
            full_question += f"\n示例输出:\n{sample_output}"
            
        # 获取编程题的详细信息（保留原函数）
        question_info = get_programming_question_info(subject, full_question, user_id)
        
        # 插入到数据库
        question_id = insert_into_db_with_conn(conn, subject, question_info, user_id)
        
        # 如果提供了session_id，则插入questions表
        if session_id:
            question_order = i + 1
            insert_into_questions_with_conn(conn, session_id, question_text, 20, question_order, question_id)
        
        solutions.append(question_info['reference_solution'])
        answers.append("")  # 保持与原函数返回格式一致
    
    # 关闭数据库连接
    conn.close()
    
    return answers, solutions

def get_programming_question_info(subject, question, user_id):
    # 使用更精确的提示获取详细信息
    line1 = f"{question}"
    line2 = """分析以下编程题并以JSON格式返回详细信息：
{
    \"sample_input\": \"只包含示例输入数据，不要包含描述文字\",
    \"sample_output\": \"只包含示例输出数据，不要包含描述文字\",
    \"test_cases\": \"包含多组测试用例的输入和期望输出\",
    \"reference_solution\": \"完整的参考解答代码\",
    \"time_limit\": 1000,
    \"memory_limit\": 256,
    \"hints\": \"解题提示\"
}
注意：test_cases和reference_solution字段必须提供，这是评判题目的关键信息"""
    
    response = new(line1, line2)
    
    try:
        # 解析JSON响应
        info_data = json.loads(response)
        
        # 确保test_cases和reference_solution不为空
        if not info_data.get('test_cases'):
            # 如果AI没有提供测试用例，生成一个基本的测试用例
            info_data['test_cases'] = generate_test_cases(question, info_data.get('sample_input', ''), info_data.get('sample_output', ''))
        
        if not info_data.get('reference_solution'):
            # 如果AI没有提供参考解答，再次请求AI生成代码
            info_data['reference_solution'] = generate_solution(question)
            
        # 清理输入输出中的描述性文字
        sample_input = clean_sample_data(info_data.get('sample_input', ''))
        sample_output = clean_sample_data(info_data.get('sample_output', ''))
        
        question_info = {
            'question_text': question,
            'sample_input': sample_input,
            'sample_output': sample_output,
            'test_cases': info_data.get('test_cases', ''),
            'reference_solution': info_data.get('reference_solution', ''),
            'time_limit': info_data.get('time_limit', 1000),
            'memory_limit': info_data.get('memory_limit', 256),
            'hints': info_data.get('hints', '')
        }
    except json.JSONDecodeError:
        # 错误处理与之前相同，但添加测试用例和参考解答的生成
        question_info = {
            'question_text': question,
            'sample_input': '',
            'sample_output': '',
            'test_cases': generate_test_cases(question, '', ''),
            'reference_solution': generate_solution(question),
            'time_limit': 1000,
            'memory_limit': 256,
            'hints': ''
        }
        # 其他JSON错误处理...
    
    return question_info

# 辅助函数：清理示例数据中的描述性文字
def clean_sample_data(data):
    if not data:
        return ''
    
    # 移除常见的描述词
    patterns = [
        r'示例[:：]?\s*', r'输入[:：]?\s*', r'输出[:：]?\s*',
        r'例如[:：]?\s*', r'如[:：]?\s*', r'样例[:：]?\s*'
    ]
    
    for pattern in patterns:
        data = re.sub(pattern, '', data)
    
    return data.strip()

# 辅助函数：生成测试用例
def generate_test_cases(question, sample_input, sample_output):
    prompt = f"""
根据以下编程题，生成至少3组测试用例（输入和期望输出）:
{question}

示例输入: {sample_input}
示例输出: {sample_output}

请以JSON格式返回:
[
  {{"input": "测试输入1", "output": "期望输出1"}},
  {{"input": "测试输入2", "output": "期望输出2"}},
  {{"input": "测试输入3", "output": "期望输出3"}}
]
"""
    response = new(prompt, "只返回JSON格式的测试用例，不要添加任何解释文字")
    
    try:
        # 尝试提取JSON
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            return json_match.group()
        else:
            # 如果无法提取，返回基本测试用例结构
            if sample_input and sample_output:
                return json.dumps([{"input": sample_input, "output": sample_output}])
            else:
                return json.dumps([{"input": "1234", "output": "10"}])
    except:
        # 出错时返回基本测试用例
        return json.dumps([{"input": "1234", "output": "10"}])

# 辅助函数：生成参考解答
def generate_solution(question):
    prompt = f"""
根据以下编程题，生成一个完整的参考解答代码:
{question}

请只返回代码，不要包含任何解释。
"""
    response = new(prompt, "只返回完整的代码实现，不要添加任何解释文字")
    
    # 提取代码块
    code_match = re.search(r'```(?:java|python|c\+\+)?\s*([\s\S]*?)```', response)
    if code_match:
        return code_match.group(1).strip()
    else:
        # 如果没有代码块格式，直接返回响应
        return response.strip()

def insert_into_db_with_conn(conn, subject, question_info, user_id):
    cursor = conn.cursor()
    
    # 确保所有可能是列表的字段都被转换为JSON字符串
    test_cases = question_info.get('test_cases', '')
    if isinstance(test_cases, (list, dict)):
        test_cases = json.dumps(test_cases, ensure_ascii=False)
    
    reference_solution = question_info.get('reference_solution', '')
    if isinstance(reference_solution, (list, dict)):
        reference_solution = json.dumps(reference_solution, ensure_ascii=False)
    
    hints = question_info.get('hints', '')
    if isinstance(hints, (list, dict)):
        hints = json.dumps(hints, ensure_ascii=False)
    
    # 插入数据
    cursor.execute('''
        INSERT INTO programming_questions 
        (subject, question_text, sample_input, sample_output, test_cases, 
         reference_solution, time_limit, memory_limit, hints, score, difficulty, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    ''', (
        subject, 
        question_info['question_text'],
        question_info.get('sample_input', ''),
        question_info.get('sample_output', ''),
        test_cases,  # 确保是字符串
        reference_solution,  # 确保是字符串
        question_info.get('time_limit', 1000),
        question_info.get('memory_limit', 256),
        hints,  # 确保是字符串
        20,  # 默认分数
        3,   # 默认难度
        user_id
    ))
    
    # 获取插入的ID
    question_id = cursor.lastrowid
    conn.commit()
    
    return question_id

def insert_into_questions_with_conn(conn, session_id, question_text, score, question_order, source_question_id):
    """
    将编程题插入到questions表
    
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
        VALUES (?, 'programming', ?, ?, ?, ?, 'programming_questions')
    ''', (session_id, question_text, score, question_order, source_question_id))
    
    conn.commit()
    return cursor.lastrowid

def pro_grading(subject, session_id, student_id):
    """
    从编程题txt文件中提取学生答案，并与数据库中的参考答案进行比较
    返回：(学生答案列表, 参考答案列表, 总得分)
    """
    try:
        # 获取代码文件所在目录的路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 获取当前目录下所有txt文件
        files = [f for f in os.listdir(current_dir) if f.endswith('.txt')]
        # 匹配包含"编程"或"三"开头的文件
        pro_files = [f for f in files if re.search(r'三\.编程|编程|^三[\.．]', f)]

        if not pro_files:
            raise FileNotFoundError("未找到编程题文件")
        
        with open(os.path.join(current_dir, pro_files[0]), "r", encoding="utf-8") as f:
            Otxt = f.read()
        
        print(f"编程题文件内容前100个字符: {Otxt[:100]}")
        
        # 使用AI提取编程题和学生答案
        ai_prompt = f"""
请从以下文本中提取编程题的题号、完整题目描述和学生编写的代码，返回JSON格式。

文本内容:
{Otxt}

注意事项：
1. 题目通常以题号开始（如"题目10"或"10."），然后是题目描述。
2. 学生的代码通常包含关键字如"class"、"public"、"import"、"def"等。
3. 有些题目可能没有学生回答，这种情况下将student_code设为空字符串。
4. 一道题的描述可能有多行，确保完整提取整个题目描述。
5. 尤其注意Java代码，通常以import或public class开头，以大括号结尾。

请返回以下格式的JSON:
{{
    "questions": [
        {{
            "question_number": "1",
            "question_text": "完整的题目描述...",
            "student_code": "学生的代码，可能为空"
        }},
        {{
            "question_number": "2",
            "question_text": "完整的题目描述...",
            "student_code": "import java.util.Scanner;\\npublic class Main {{\\n  public static void main(String[] args) {{\\n    // 代码内容\\n  }}\\n}}"
        }}
    ]
}}
"""
        
        print("调用AI提取编程题...")
        ai_response = new("你是一个专业的代码分析助手，请提取文本中的编程题和学生代码", ai_prompt)
        
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
            print(f"AI成功提取了{len(extracted_questions)}道编程题")
            
            # 使用新的数据库连接方法
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 获取所有编程题
            cursor.execute('''
                SELECT id, question_text, sample_input, sample_output, test_cases, 
                       reference_solution, score FROM programming_questions 
                WHERE subject = ?
            ''', (subject,))
            
            db_questions = cursor.fetchall()
            
            # 准备返回值
            student_solutions = []
            reference_answers = []
            question_ids = []
            total_score = 0
            
            # 处理每道题目
            for q in extracted_questions:
                question_number = q.get("question_number", "")
                question_text = q.get("question_text", "")
                student_code = q.get("student_code", "").strip()
                
                print(f"处理题目 {question_number}: {question_text[:50]}...")
                print(f"学生代码长度: {len(student_code)} 字符")
                
                # 添加到结果列表
                student_solutions.append(student_code)
                
                # 变量初始化
                matched_question_id = None
                ai_feedback = ""
                source_max_score = 20  # 默认分值
                reference_solution = "未找到匹配题目，使用AI直接评分"
                
                # 查找匹配的题目
                highest_similarity = 0
                for db_q in db_questions:
                    q_id, q_text, q_input, q_output, q_tests, q_solution, q_score = db_q
                    
                    # 计算相似度分数
                    similarity = 0
                    
                    # 1. 检查题号
                    db_num_match = re.match(r'^(\d+)[、.．]\s*', q_text)
                    db_num = db_num_match.group(1) if db_num_match else ""
                    
                    if question_number and db_num and question_number == db_num:
                        similarity = 1.0  # 完全匹配
                        print(f"题号匹配成功: {question_number}")
                    else:
                        # 2. 关键词匹配
                        clean_q_text = q_text.lower().replace(" ", "")
                        clean_desc = question_text.lower().replace(" ", "")
                        
                        # 提取关键词
                        keywords = ["整数", "for", "语句", "循环", "输入", "输出", "sum", "average", "平均"]
                        keyword_matches = 0
                        for keyword in keywords:
                            if keyword in clean_q_text and keyword in clean_desc:
                                keyword_matches += 1
                        
                        if keyword_matches > 0:
                            similarity = keyword_matches / len(keywords)
                        
                        # 3. 示例输入/输出匹配
                        if q_input and q_input in question_text:
                            similarity += 0.2
                        if q_output and q_output in question_text:
                            similarity += 0.2
                    
                    # 更新最佳匹配
                    if similarity > highest_similarity:
                        highest_similarity = similarity
                        matched_question_id = q_id
                        reference_solution = q_solution
                        source_max_score = q_score
                
                # 如果找到匹配的题目
                if matched_question_id and highest_similarity > 0.3:
                    print(f"题目匹配成功，相似度: {highest_similarity:.2f}")
                    question_ids.append(matched_question_id)
                    reference_answers.append(reference_solution)
                    
                    # 从questions表获取该题的分数
                    question_score = get_question_score(conn, session_id, matched_question_id, 'programming_questions')
                    
                    if question_score is not None:
                        print(f"从questions表获取到分数: {question_score}")
                        source_max_score = question_score
                    
                    # 提示信息
                    if reference_solution:
                        print(f"使用匹配题目的参考解答")
                    else:
                        print(f"匹配的题目没有参考解答，使用AI评分")
                else:
                    # 使用AI评分
                    print(f"未找到匹配题目，使用AI直接评分")
                    question_ids.append(None)
                    reference_answers.append("AI评分，无参考答案")
                
                # 开始评分
                if student_code:
                    # 构建AI评分提示
                    ai_prompt = f"""
你是一名专业的编程老师，请评估以下学生代码的质量。

题目要求: {question_text}

参考答案:
{reference_solution if reference_solution != "未找到匹配题目，使用AI直接评分" else "无参考答案"}

学生代码:
{student_code}

评估维度:
1. 功能正确性：代码是否实现了所需功能 (40%)
2. 代码质量：代码结构、可读性和效率 (30%)
3. 编程风格：命名规范、缩进和注释 (20%)
4. 错误处理：是否考虑了边界条件和异常情况 (10%)

请根据以上维度评估代码，提供具体反馈，并给出0-{source_max_score}分的评分。请直接以如下格式给出评分：
分数: X/{source_max_score}

然后提供详细的评价。
"""
                    
                    ai_response = new("你是一名专业的编程老师，正在评判学生的编程题", ai_prompt)
                    
                    # 提取分数
                    score_match = re.search(r'分数: (\d+)[^\d]*' + str(source_max_score), ai_response)
                    if score_match:
                        score = int(score_match.group(1))
                        print(f"AI评分: {score}/{source_max_score}")
                    else:
                        score_match = re.search(r'(\d+)[^\d]*分', ai_response)
                        if score_match:
                            score = int(score_match.group(1))
                            if score > source_max_score:
                                score = source_max_score  # 确保不超过最大分数
                            print(f"通过匹配提取到分数: {score}")
                        else:
                            # 默认给一半分数
                            score = source_max_score // 2
                            print(f"未找到明确分数，使用默认分数: {score}")
                    
                    # 更新总分
                    total_score += score
                    
                    # 生成AI反馈
                    ai_feedback = ai_response.replace(f"分数: {score}/{source_max_score}", "").strip()
                    if not ai_feedback:
                        ai_feedback = f"代码已得分: {score}/{source_max_score}"
                    
                    # 如果提供了session_id和student_id，保存到数据库
                    if session_id and student_id:
                        try:
                            # 如果没有匹配到已有题目，创建新题目
                            if not matched_question_id:
                                new_question_id = insert_question_to_db(
                                    conn, 
                                    session_id, 
                                    'programming', 
                                    question_text, 
                                    source_max_score
                                )
                                matched_question_id = new_question_id
                            
                            # 获取题目在questions表中的ID
                            q_id = get_question_id(conn, session_id, matched_question_id, 'programming_questions')
                            if not q_id:
                                q_id = matched_question_id
                            
                            # 准备评分详情
                            scoring_details = json.dumps({
                                "max_score": source_max_score,
                                "earned_score": score,
                                "ai_feedback": ai_feedback,
                                "ai_graded": True
                            })
                            
                            # 插入student_answers表
                            insert_student_answers_to_db(
                                conn, 
                                session_id, 
                                student_id, 
                                q_id, 
                                'programming', 
                                student_code, 
                                score,
                                ai_feedback[:200] + "..." if len(ai_feedback) > 200 else ai_feedback,
                                scoring_details
                            )
                            print(f"编程题评分结果已保存到数据库: 题目ID={q_id}, 学生ID={student_id}")
                            
                        except Exception as e:
                            import traceback
                            print(f"保存编程题评分结果到数据库失败: {str(e)}")
                            print(traceback.format_exc())
                else:
                    # 学生未作答
                    print(f"学生未提交代码")
                    ai_feedback = "未提交代码"
                    reference_answers.append("未提交")
                    
                    # 即使未作答也保存到数据库
                    if session_id and student_id:
                        try:
                            # 如果没有匹配到已有题目，创建新题目
                            if not matched_question_id:
                                new_question_id = insert_question_to_db(
                                    conn, 
                                    session_id, 
                                    'programming', 
                                    question_text, 
                                    source_max_score
                                )
                                matched_question_id = new_question_id
                            
                            # 获取题目在questions表中的ID
                            q_id = get_question_id(conn, session_id, matched_question_id, 'programming_questions')
                            if not q_id:
                                q_id = matched_question_id
                            
                            # 准备评分详情
                            scoring_details = json.dumps({
                                "max_score": source_max_score,
                                "earned_score": 0,  # 未提交代码得0分
                                "ai_feedback": "学生未提交代码",
                                "ai_graded": True
                            })
                            
                            # 插入student_answers表，空代码
                            insert_student_answers_to_db(
                                conn, 
                                session_id, 
                                student_id, 
                                q_id, 
                                'programming', 
                                "", 
                                0,  # 0分
                                "未提交代码，得分: 0/" + str(source_max_score),
                                scoring_details
                            )
                            print(f"未提交代码的记录已保存到数据库: 题目ID={q_id}, 学生ID={student_id}")
                        except Exception as e:
                            import traceback
                            print(f"保存未作答记录到数据库失败: {str(e)}")
                            print(traceback.format_exc())
            
            # 关闭数据库连接
            conn.close()
            
            # 打印结果
            print(f"编程题评分完成，总分: {total_score}")
            
            return student_solutions, reference_answers, total_score
            
        except Exception as e:
            import traceback
            print(f"AI提取编程题失败: {str(e)}")
            print(traceback.format_exc())
            print("回退到传统分割方法...")
            
            # 如果AI提取失败，可以回退到传统方法
            # ... [可以保留原始代码作为备用] ...
            return ["解析失败"], ["解析失败"], 0
            
    except Exception as e:
        import traceback
        print(f"编程题评分失败: {str(e)}")
        print(traceback.format_exc())
        return [], [], 0

if __name__ == '__main__':
    pro_grading("java", 1, 1)

