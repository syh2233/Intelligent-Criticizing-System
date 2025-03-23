import sqlite3

# 连接到数据库
conn = sqlite3.connect('database/It_g.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 获取考试session列表
cursor.execute("SELECT id, name, subject FROM exam_sessions")
sessions = cursor.fetchall()
print("可用的考试:")
for session in sessions:
    print(f"ID: {session['id']}, 名称: {session['name']}, 科目: {session['subject']}")

print("\n学生答案数据:")
# 查询答案数据
cursor.execute("""
    SELECT sa.session_id, es.name as exam_name, sa.student_id, s.name as student_name, 
           sa.question_id, q.question_text, sa.question_type, sa.answer_text, 
           sa.ai_score, sa.final_score, sa.ai_feedback
    FROM student_answers sa
    JOIN exam_sessions es ON sa.session_id = es.id
    JOIN students s ON sa.student_id = s.id
    JOIN questions q ON sa.question_id = q.id
    ORDER BY sa.session_id, sa.student_id, sa.question_id
    LIMIT 20
""")
answers = cursor.fetchall()

for a in answers:
    print(f"考试ID: {a['session_id']}, 考试名称: {a['exam_name']}")
    print(f"学生ID: {a['student_id']}, 学生名称: {a['student_name']}")
    print(f"题目ID: {a['question_id']}, 题目内容: {a['question_text'][:30]}...")
    print(f"题目类型: {a['question_type']}")
    print(f"答案: {a['answer_text']}")
    print(f"AI评分: {a['ai_score']}, 最终得分: {a['final_score']}")
    print(f"反馈: {a['ai_feedback']}")
    print("-" * 80)

# 检查最近添加的测试数据
python_exam_id = None
for session in sessions:
    if session['name'] == 'Python测试':
        python_exam_id = session['id']
        break

if python_exam_id:
    print(f"\n检查Python测试考试(ID={python_exam_id})的数据:")
    cursor.execute("""
        SELECT sa.session_id, sa.student_id, s.name as student_name, 
               sa.question_id, q.question_text, sa.question_type, sa.answer_text, 
               sa.ai_score, sa.final_score, sa.ai_feedback, sa.manual_feedback
        FROM student_answers sa
        JOIN students s ON sa.student_id = s.id
        JOIN questions q ON sa.question_id = q.id
        WHERE sa.session_id = ?
        ORDER BY sa.student_id, sa.question_id
    """, (python_exam_id,))
    test_answers = cursor.fetchall()
    
    if test_answers:
        for a in test_answers:
            print(f"学生ID: {a['student_id']}, 学生名称: {a['student_name']}")
            print(f"题目ID: {a['question_id']}, 题目内容: {a['question_text'][:30]}...")
            print(f"题目类型: {a['question_type']}")
            print(f"答案: {a['answer_text']}")
            print(f"AI评分: {a['ai_score']}, 最终得分: {a['final_score']}")
            print(f"AI反馈: {a['ai_feedback']}")
            print(f"人工反馈: {a['manual_feedback']}")
            print("-" * 80)
    else:
        print("未找到Python测试考试的答案数据。")

# 关闭连接
conn.close() 