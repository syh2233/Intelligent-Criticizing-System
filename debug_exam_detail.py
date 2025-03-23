import sqlite3
import json
from datetime import datetime

def execute_query(query, params=None):
    conn = sqlite3.connect('database/It_g.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        result = cursor.fetchall()
        # 转换为字典列表，方便打印
        dict_result = [dict(row) for row in result]
        return True, dict_result
    except Exception as e:
        print(f"查询出错: {e}")
        return False, None
    finally:
        conn.close()

def debug_exam_detail(exam_id):
    print(f"测试考试ID {exam_id} 的详情页面")
    
    # 获取考试基本信息
    exam_query = """
        SELECT id, name, subject, duration, exam_score as total_score, start_time, end_time
        FROM exam_sessions
        WHERE id = ?
    """
    success, exam_data = execute_query(exam_query, (exam_id,))
    
    if not success or not exam_data:
        print(f"未找到考试ID {exam_id} 的信息")
        return
    
    print(f"考试基本信息: {json.dumps(exam_data, indent=2, ensure_ascii=False)}")
    
    # 假设当前用户名
    user_email = "test@example.com"
    
    # 获取学生信息
    student_query = """
        SELECT id FROM students WHERE student_id = ? OR name = ?
    """
    success, student_data = execute_query(student_query, (user_email, user_email))
    
    if not success or not student_data:
        print(f"未找到学生 {user_email}")
        return
    
    student_id = student_data[0]['id']
    print(f"学生ID: {student_id}")
    
    # 获取学生在该考试的总分
    score_query = """
        SELECT SUM(final_score) as total_score 
        FROM student_answers 
        WHERE student_id = ? AND session_id = ?
    """
    success, score_data = execute_query(score_query, (student_id, exam_id))
    
    total_score = score_data[0]['total_score'] if success and score_data and score_data[0]['total_score'] else None
    print(f"学生总分: {total_score}")
    
    # 获取考试中的所有题目
    questions_query = """
        SELECT id, question_type, question_text, score, question_order
        FROM questions
        WHERE session_id = ?
        ORDER BY question_order
    """
    success, questions = execute_query(questions_query, (exam_id,))
    
    if not success or not questions:
        print(f"考试ID {exam_id} 没有题目")
        return
    
    print(f"找到 {len(questions)} 个题目")
    
    # 获取每个题目的学生答案
    for q in questions:
        print(f"\n题目ID: {q['id']}, 类型: {q['question_type']}, 分值: {q['score']}")
        print(f"题目内容: {q['question_text'][:50]}...")
        
        # 获取学生对该题的作答
        answer_query = """
            SELECT answer_text, ai_score, ai_feedback, scoring_details, final_score, manual_feedback
            FROM student_answers
            WHERE session_id = ? AND question_id = ? AND student_id = ?
        """
        success, answer = execute_query(answer_query, (exam_id, q['id'], student_id))
        
        if success and answer:
            print(f"找到学生答案: {json.dumps(answer[0], indent=2, ensure_ascii=False)}")
        else:
            print("未找到该题的学生答案")


# 获取Python测试考试的ID
query = "SELECT id FROM exam_sessions WHERE name = 'Python测试'"
success, result = execute_query(query)

if success and result:
    python_exam_id = result[0]['id']
    print(f"找到Python测试考试，ID: {python_exam_id}")
    debug_exam_detail(python_exam_id)
else:
    # 测试ID 8和10
    print("尝试检查ID为8和10的考试")
    debug_exam_detail(8)
    print("\n" + "="*80 + "\n")
    debug_exam_detail(10) 