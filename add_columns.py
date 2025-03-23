import sqlite3

# 连接到数据库
conn = sqlite3.connect('database/It_g.db')
cursor = conn.cursor()

# 查看表结构
cursor.execute("PRAGMA table_info(student_answers)")
columns = cursor.fetchall()
column_names = [col[1] for col in columns]

# 添加缺失的列
if 'final_score' not in column_names:
    print("添加final_score列...")
    cursor.execute("ALTER TABLE student_answers ADD COLUMN final_score REAL CHECK(final_score >= 0)")

if 'manual_feedback' not in column_names:
    print("添加manual_feedback列...")
    cursor.execute("ALTER TABLE student_answers ADD COLUMN manual_feedback TEXT")

# 提交更改
conn.commit()

# 关闭连接
conn.close()

print("完成！") 