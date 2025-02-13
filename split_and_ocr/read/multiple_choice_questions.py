from split_and_ocr.ai import aiapi
import re
import os
import sqlite3


def choice_readexit():
    # 获取当前目录下所有txt文件
    files = [f for f in os.listdir() if f.endswith('.txt')]
    # 匹配包含"选择"且文件名长度大于2的文件
    fill_files = [f for f in files if re.search(r'选择.+', f)]

    if not fill_files:
        raise FileNotFoundError("未找到包含'选择'的文件")
    with open(fill_files[0], "r", encoding="utf-8") as f:
        Otxt = f.readlines()
    f.close()
    admittxt = ""
    line = f"{Otxt}是试卷选择题题目，请对题目进行整理，输出原试卷，不进行补充答案但矫正和但补充题目包括补充括号且将括号全换位中文括号，只输出题目，识别到的其他题目也去除,题和题之间用---分割"
    admittxt = aiapi(admittxt, line)
    admittxt = admittxt[admittxt.find('\n') + 1:] if '\n' in admittxt else admittxt
    answers = re.findall(r'\（(.*?)\）', admittxt)
    answers = [answer for answer in answers if re.match(r'^[A-Za-z\s]*$', answer)]
    print(answers)
    aa = []
    for i in admittxt.split("---"):
        i = re.sub(r'\([^)]*\)', ' ', i)
        answer = ""
        line = f"{i}是试卷选择题题目，输出标准答案只输出答案不要有后面的原题选项"
        answer = aiapi(answer, line)
        aa.append(answer)
        answer2 = ""
        line2 = f"{i}是试卷选择题题目，请将题目和每个选项之间都用---分割，输出格式为xxx换行---换行A:xxx换行---换行B:xxx换行---换行C:xxx换行---换行D:xxx，不要输出其他任何语句"
        answer2 = aiapi(answer2, line2)
        print(answer2)
        qt,A,B,C,D = answer2.split("---")
        # 插入到数据库
        insert_into_db(qt, A,B,C,D,answer)
    print(aa)
    return answers, aa


def insert_into_db(question_text, option_a, option_b, option_c, option_d, correct_answer):
    # 连接到SQLite数据库
    conn = sqlite3.connect('../../database/It_g.db')
    cursor = conn.cursor()

    # 插入数据
    cursor.execute('''
        INSERT INTO multiple_choice_questions 
        (subject, question_text, option_a, option_b, option_c, option_d, 
         correct_answer, score, difficulty, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    ''', ('python', question_text, option_a, option_b, option_c, option_d, correct_answer, 5, 3))

    # 提交事务并关闭连接
    conn.commit()
    conn.close()


if __name__ == '__main__':
    answers, aa = choice_readexit()
    print(answers, aa)