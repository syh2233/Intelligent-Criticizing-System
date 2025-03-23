import sqlite3

# 连接到数据库
conn = sqlite3.connect('database/It_g.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 查找Python测试考试
cursor.execute("SELECT id, name, subject, status FROM exam_sessions WHERE name LIKE '%Python%'")
python_exams = cursor.fetchall()

if not python_exams:
    print("未找到任何Python相关的考试")
    conn.close()
    exit()

print("找到以下Python相关考试:")
for exam in python_exams:
    print(f"ID: {exam['id']}, 名称: {exam['name']}, 科目: {exam['subject']}, 状态: {exam['status']}")
    
    # 检查该考试的题目
    cursor.execute("""
        SELECT id, question_type, question_text, score 
        FROM questions 
        WHERE session_id = ? 
        ORDER BY question_order
    """, (exam['id'],))
    questions = cursor.fetchall()
    
    if questions:
        print(f"\n考试ID {exam['id']} 的题目:")
        for q in questions:
            print(f"  题目ID: {q['id']}, 类型: {q['question_type']}, 分值: {q['score']}, 内容: {q['question_text'][:30]}...")
    else:
        print(f"\n考试ID {exam['id']} 没有设置题目")
    
    # 检查该考试的学生答案
    cursor.execute("""
        SELECT DISTINCT student_id, s.name as student_name
        FROM student_answers sa
        JOIN students s ON sa.student_id = s.id
        WHERE sa.session_id = ?
    """, (exam['id'],))
    students = cursor.fetchall()
    
    if students:
        print(f"\n考试ID {exam['id']} 的学生回答:")
        for student in students:
            print(f"  学生ID: {student['student_id']}, 姓名: {student['student_name']}")
            
            cursor.execute("""
                SELECT sa.question_id, q.question_text, sa.answer_text, sa.ai_score, sa.final_score
                FROM student_answers sa
                JOIN questions q ON sa.question_id = q.id
                WHERE sa.session_id = ? AND sa.student_id = ?
                ORDER BY q.question_order
            """, (exam['id'], student['student_id']))
            answers = cursor.fetchall()
            
            for a in answers:
                print(f"    题目ID: {a['question_id']}, 答案: {a['answer_text'][:20]}..., AI分数: {a['ai_score']}, 最终分数: {a['final_score']}")
    else:
        print(f"\n考试ID {exam['id']} 没有学生回答")

# 检查页面加载时使用的exam_detail路由和参数
print("\n检查考试详情页面的路由参数:")
cursor.execute("SELECT * FROM sqlite_master WHERE type='table' AND name='sessions'")
if cursor.fetchone():
    cursor.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT 5")
    sessions = cursor.fetchall()
    if sessions:
        print("最近的会话:")
        for s in sessions:
            print(f"  会话ID: {s['id']}, 用户信息: {s.get('user_id') or s.get('email')}")
    else:
        print("没有找到会话记录")
else:
    print("没有sessions表")

# 关闭连接
conn.close() 