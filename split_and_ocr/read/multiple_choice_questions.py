from split_and_ocr.ai import aiapi
from split_and_ocr.ai import new
import re
import os
import sqlite3


def choice_readexit(subject, user_id):
    # 获取当前目录下所有txt文件
    files = [f for f in os.listdir() if f.endswith('.txt')]
    # 匹配包含"选择"且文件名长度大于2的文件
    fill_files = [f for f in files if re.search(r'选择.+', f)]

    if not fill_files:
        raise FileNotFoundError("未找到包含'选择'的文件")
    with open(fill_files[0], "r", encoding="utf-8") as f:
        Otxt = f.read()
    f.close()
    line_1 = f"{Otxt}"
    line_2 = "上述是试卷选择题题目，请对题目进行整理，输出原试卷，不进行补充答案但矫正和但补充题目包括补充括号且将括号全换位中文括号，例如：下列选项中，关于异常的描述错误的是()，换成，下列选项中，关于异常的描述错误的是（）；只输出题目，识别到的其他题目也去除,题和题之间用---分割,强调是题和题分割，例如：下列选项中，不是 Python 语言特点的是()。\nA.简洁B.开源C.面向过程D.可移植\n---\n下列哪个不是Python的应用领域?()\nA.Web 开发B.科学计算C.游戏开发"
    admittxt = new(line_1, line_2)
    admittxt = admittxt[admittxt.find('：\n') + 1:] if '\n' in admittxt else admittxt
    admittxt = admittxt[admittxt.find('\n') + 1:] if '\n' in admittxt else admittxt
    # print(admittxt)
    answers = re.findall(r'\（(.*?)\）', admittxt)
    if len(answers)==0:
        answers = re.findall(r'\((.*?)\)', admittxt)
    answers = [answer for answer in answers if re.match(r'^[A-Za-z\s]*$', answer)]
    print(answers)
    aa = []
    admittxt = admittxt.split("---")
    print(admittxt)
    for i in admittxt:
        if len(i)<5:
            continue
        # i = re.sub(r'\([^)]*\)', ' ', i)
        line1 = f"{i}"
        line2 = f"是试卷选择题题目，输出标准答案只输出答案不要有后面的原题选项"
        answer1 = new(line1, line2)
        print(answer1)
        aa.append(answer1)
        len1 = f"{i}"
        len2 = "是试卷选择题题目，请将题目和每个选项之间都用---分割，输出格式为xxx换行---换行A:xxx换行---换行B:xxx换行---换行C:xxx换行---换行D:xxx，不要输出其他任何语句"
        answer2 = new(len1, len2)
        print(answer2)
        try:
            qt,A,B,C,D = answer2.split("---")
        except:
            qt, A, B, C = answer2.split("---")
            D = ""
        # 插入到数据库
        insert_into_db(subject, qt, A,B,C,D,answer1, user_id)
    # print(aa)
    return answers, aa


def insert_into_db(subject, question_text, option_a, option_b, option_c, option_d, correct_answer,user_id):
    # 连接到SQLite数据库
    conn = sqlite3.connect('../../database/It_g.db')
    cursor = conn.cursor()

    # 插入数据
    cursor.execute('''
        INSERT INTO multiple_choice_questions 
        (subject, question_text, option_a, option_b, option_c, option_d, 
         correct_answer, score, difficulty, created_by , created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    ''', (subject, question_text, option_a, option_b, option_c, option_d, correct_answer, 5, 3, user_id))

    # 提交事务并关闭连接
    conn.commit()
    conn.close()


if __name__ == '__main__':
    answers, aa = choice_readexit("python", 3)
    print(answers, aa)