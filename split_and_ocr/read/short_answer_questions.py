from split_and_ocr.ai import new
import re
import os
import sqlite3


def answer_readexit(subject, user_id):
    # 获取当前目录下所有txt文件
    files = [f for f in os.listdir() if f.endswith('.txt')]
    # 匹配包含"简答"且文件名长度大于2的文件
    fill_files = [f for f in files if re.search(r'简答.+', f)]

    if not fill_files:
        raise FileNotFoundError("未找到包含'简答'的文件")
    with open(fill_files[0], "r", encoding="utf-8") as f:
        Otxt = f.readlines()
    f.close()
    line1 = f"{Otxt}"
    line2 = "是试卷简答题题目，请对题目进行整理，输出原试卷，不进行补充答案但矫正和但补充题目，只输出题目，识别到的其他题目也去除,每题和每题之间用----分割，每题里的题目和答案之间用---分割，每题里只有题目没有答案就不用---分割"
    admittxt = new(line1, line2)
    admittxt = admittxt[admittxt.find('\n') + 1:] if '\n' in admittxt else admittxt
    print(admittxt)
    aa = []
    bb = []
    for i in admittxt.split("----"):
        try:
            a,b = i.split("---")
        except:
            a=i
            b=""
        if a == "":
            continue
        bb.append(b)
        line_1 = f"{a}"
        line_2 = "是试卷简答题题目，请给出标准参考答案，要求详细完整"
        answer = new(line_1, line_2)

        line__1 = f"{a}"
        line__2 = "是试卷简答题题目，请给出考点关键词用|分隔开，要求只输出关键词"
        answer2 = new(line__1, line__2)
        aa.append(answer2)
        # 插入到数据库
        insert_into_db(subject, i.strip(), answer.strip(),answer2.strip(), user_id)
    print(bb)
    print(aa)
    return bb,aa


def insert_into_db(subject, question_text, reference_answer,key_points, user_id):
    # 连接到SQLite数据库
    conn = sqlite3.connect('../../database/It_g.db')
    cursor = conn.cursor()

    # 插入数据到short_answer_questions表
    cursor.execute('''
        INSERT INTO short_answer_questions 
        (subject, question_text, reference_answer, key_points, score, difficulty, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    ''', (subject, question_text, reference_answer, key_points, 10, 3, user_id))

    # 提交事务并关闭连接
    conn.commit()
    conn.close()

if __name__ == '__main__':
    answer_readexit("python", 3)