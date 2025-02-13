from split_and_ocr.ai import aiapi
import re
import os
import sqlite3


def ofill_readexit():
    # 获取当前目录下所有txt文件
    files = [f for f in os.listdir() if f.endswith('.txt')]
    # 匹配包含"填空"且文件名长度大于2的文件
    fill_files = [f for f in files if re.search(r'填空.+', f)]

    if not fill_files:
        raise FileNotFoundError("未找到包含'填空'的文件")
    with open(fill_files[0], "r", encoding="utf-8") as f:
        Otxt = f.readlines()
    f.close()
    admittxt = ""
    line = f"{Otxt}是试卷填空题题目，请对题目进行整理，输出原试卷，不进行补充答案但矫正和补充题目只输出题目，识别到的其他题目也去除,题和题之间用---分割"
    admittxt = aiapi(admittxt, line)
    admittxt = admittxt[admittxt.find('\n') + 1:] if '\n' in admittxt else admittxt
    print(admittxt)
    aa = []
    for i in admittxt.split("---"):
        # ai获取答案
        answer = ""
        line = f"{i}是试卷填空题题目，输出标准答案只输出答案，每一题的答案用|分隔开，单个答案不用|隔开，不包含原题"
        answer = aiapi(answer, line)
        aa.append(answer.replace("或", ""))
        # 插入到数据库
        insert_into_db(i, answer)
    print(aa)
    return aa

def fill_readexit():
    # 获取当前目录下所有txt文件
    files = [f for f in os.listdir() if f.endswith('.txt')]
    # 匹配包含"填空"且文件名长度大于2的文件
    fill_files = [f for f in files if re.search(r'填空.+', f)]
    
    if not fill_files:
        raise FileNotFoundError("未找到包含'填空'的文件")
    with open(fill_files[0], "r", encoding="utf-8") as f:
        Otxt = f.readlines()
    f.close()
    admittxt = ""
    line = f"{Otxt}是试卷填空题题目，请对题目进行整理，输出原试卷，不进行补充答案但矫正和补充题目只输出题目，识别到的其他题目也去除,题和题之间用---分割"
    admittxt = aiapi(admittxt,line)
    admittxt = admittxt[admittxt.find('\n')+1:] if '\n' in admittxt else admittxt
    print(admittxt)
    aa = []
    bb = []

    # 连接到SQLite数据库
    conn = sqlite3.connect('../../database/It_g.db')
    cursor = conn.cursor()
    for i in admittxt.split("---"):
        print(i)
        # 从数据库中查询原题
        cursor.execute('''
            SELECT question_text FROM fill_blank_questions 
            WHERE question_text LIKE ? OR question_text LIKE ?
        ''', (i.replace('______', '%'), i))
        original_question = cursor.fetchone()
        
        # i.replace("  ", "")
        ma = re.findall(r"______", original_question)
        if len(ma)==1:
            matches = re.findall(r"(.*?)______(.*)", original_question)
            b = re.findall(rf"{matches[0][0]}(.*){matches[0][1]}", i)
            try:
                bb.append(f"{b[0]}".replace("_", "").replace("\n", ""))
            except:
                matches = re.findall(r"(.*?)______", original_question)
                b = i.replace(matches[0], "").replace("_", "").replace("\n", "")
                bb.append(b)
        elif len(ma)==2:
            matches = re.findall(r"(.*?)______(.*?)______(.*)", original_question)
            b = re.findall(rf"{matches[0][0]}(.*?){matches[0][1]}(.*){matches[0][2]}", i)
            bb.append(f"{b[0][0]}|{b[0][1]}".replace("_", "").replace("\n", ""))
        elif len(ma)==3:
            matches = re.findall(r"(.*?)______(.*?)______(.*?)______(.*)", original_question)
            b = re.findall(rf"{matches[0][0]}(.*?){matches[0][1]}(.*?){matches[0][2]}(.*){matches[0][3]}", i)
            bb.append(f"{b[0][0]}|{b[0][1]}|{b[0][2]}".replace("_", "").replace("\n", ""))
        elif len(ma)==4:
            matches = re.findall(r"(.*?)______(.*?)______(.*?)______(.*?)______(.*)", original_question)
            b = re.findall(rf"{matches[0][0]}(.*?){matches[0][1]}(.*?){matches[0][2]}(.*?){matches[0][3]}(.*){matches[0][3]}", i)
            bb.append(f"{b[0][0]}|{b[0][1]}|{b[0][2]}|{b[0][3]}".replace("_", "").replace("\n", ""))
        else:
            # b = ""
            # bb.append(b)
            print("匹配失败")
            continue
        # 从数据库中查询答案
        cursor.execute('''
            SELECT correct_answer FROM fill_blank_questions 
            WHERE question_text = ?
        ''', (i,))
        result = cursor.fetchone()

        if result:
            # 如果在数据库中找到答案，直接使用
            answer = result[0]
        else:
            # 如果数据库中没有，则使用AI生成答案并插入数据库
            answer = ""
            line = f"{i}是试卷填空题题目，输出标准答案只输出答案，每一题的答案用|分隔开，单个答案不用|隔开，不包含原题"
            answer = aiapi(answer, line)
            # 插入到数据库
            insert_into_db(i, answer)

        aa.append(answer.replace("或", ""))

        # 关闭数据库连接
        conn.close()
    print(aa)
    print(bb)
    return bb,aa


def insert_into_db(question_text, correct_answer):
    # 连接到SQLite数据库
    conn = sqlite3.connect('../../database/It_g.db')
    cursor = conn.cursor()
    
    # 插入数据
    cursor.execute('''
        INSERT INTO fill_blank_questions (subject, question_text, correct_answer, alternative_answers, score, difficulty, created_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    ''', ('python', question_text, correct_answer, '', 5, 3))
    
    # 提交事务并关闭连接
    conn.commit()
    conn.close()

if __name__ == '__main__':
    fill_readexit()