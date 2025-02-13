import sqlite3

# 连接到SQLite数据库（如果数据库不存在，则会自动创建）
conn = sqlite3.connect('database/It_g.db')
cursor = conn.cursor()

# 插入数据到 students 表
cursor.execute('''
    INSERT INTO students (name, student_id)
    VALUES (?, ?)
''', ('张三', 'S12345'))

# 插入数据到 questions 表
cursor.execute('''
    INSERT INTO questions (session_id, question_text, score, question_order)
    VALUES (?, ?, ?, ?)
''', (1, '什么是Python的GIL？', 10, 1))

# 插入数据到 student_answers 表
cursor.execute('''
    INSERT INTO student_answers (session_id, student_id, question_id, answer_text, ai_score, ai_feedback, final_score, review_status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
''', (1, 1, 1, 'GIL是全局解释器锁，它确保同一时间只有一个线程执行Python字节码。', 8, '回答正确，但可以更详细。', 8, 'reviewed'))

# 提交事务
conn.commit()

# 关闭连接
conn.close()