from split_and_ocr.ai import aiapi
import re
import os
import sqlite3


def tf_readexit():
    # 获取当前目录下所有txt文件
    files = [f for f in os.listdir() if f.endswith('.txt')]
    # 匹配包含"判断"且文件名长度大于2的文件
    fill_files = [f for f in files if re.search(r'判断.+', f)]

    if not fill_files:
        raise FileNotFoundError("未找到包含'判断'的文件")
    with open(fill_files[0], "r", encoding="utf-8") as f:
        Otxt = f.readlines()
    f.close()
    admittxt = ""
    line = f"{Otxt}是试卷判断题题目，请对题目进行整理，输出原试卷，不进行补充答案但矫正和但补充题目包括补充括号且将括号全换位中文括号，只输出题目，识别到的其他题目也去除,题和题之间用---分割"
    admittxt = aiapi(admittxt, line)
    admittxt = admittxt[admittxt.find('\n') + 1:] if '\n' in admittxt else admittxt
    print(admittxt)
    answers = re.findall(r'\（(.*?)\）', admittxt)
    print(answers)
    aa = []
    for i in admittxt.split("---"):
        i = re.sub(r'\([^)]*\)', ' ', i)
        answer = ""
        line = f"{i}是试卷判断题题目，输出标准答案，只输出'对'或'错'，不要有其他内容"
        answer = aiapi(answer, line)
        aa.append(answer)
        # 对于判断题，我们只需要题目和答案
        # 插入到数据库
        insert_into_db(i.strip(), answer.strip())
    print(aa)
    return answers, aa

def insert_into_db(question_text, correct_answer):
    # 连接到SQLite数据库
    conn = sqlite3.connect('../../database/It_g.db')
    cursor = conn.cursor()

    # 插入数据到true_false_questions表
    cursor.execute('''
        INSERT INTO true_false_questions 
        (subject, question_text, correct_answer, explanation, score, difficulty, created_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    ''', ('python', question_text, correct_answer, '', 5, 3))

    # 提交事务并关闭连接
    conn.commit()
    conn.close()

if __name__ == '__main__':
    answers, aa = tf_readexit()
    print(answers, aa)