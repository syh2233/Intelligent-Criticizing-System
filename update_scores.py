import sqlite3

# 连接到数据库
conn = sqlite3.connect('database/It_g.db')
cursor = conn.cursor()

# 更新final_score列，如果为null则使用ai_score的值
cursor.execute("""
    UPDATE student_answers 
    SET final_score = ai_score 
    WHERE final_score IS NULL AND ai_score IS NOT NULL
""")

# 提交更改
conn.commit()

# 检查更新了多少行
cursor.execute("SELECT COUNT(*) FROM student_answers WHERE final_score IS NOT NULL")
count = cursor.fetchone()[0]
print(f"已更新 {count} 行数据")

# 关闭连接
conn.close() 