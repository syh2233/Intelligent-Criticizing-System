from split_and_ocr.ai import aiapi
import re
import os
import sqlite3


def pro_readexit():
    # 获取当前目录下所有txt文件
    files = [f for f in os.listdir() if f.endswith('.txt')]
    # 匹配包含"编程"且文件名长度大于2的文件
    fill_files = [f for f in files if re.search(r'编程.+', f)]

    if not fill_files:
        raise FileNotFoundError("未找到包含'编程'的文件")
    with open(fill_files[0], "r", encoding="utf-8") as f:
        Otxt = f.readlines()
    f.close()
    admittxt = ""
    line = f"{Otxt}是试卷编程题题目，请对题目进行整理，输出原试卷，不进行补充答案但矫正和但补充题目，只输出题目，识别到的其他题目也去除,题和题之间用----分割，题和答案之间用---分割"
    admittxt = aiapi(admittxt, line)
    admittxt = admittxt[admittxt.find('\n') + 1:] if '\n' in admittxt else admittxt
    print(admittxt)
    aa=[]
    bb=[]
    for i in admittxt.split("----"):
        try:
            a,b = i.split("---")
        except:
            b = ""
        if not i.strip():
            continue
            
        # 获取编程题的详细信息
        question_info = get_programming_question_info(i.strip())
        # 插入到数据库
        insert_into_db(question_info)
        bb.append(b)
        aa.append(question_info['reference_solution'])
    return bb,aa


def get_programming_question_info(question):
    """获取编程题的详细信息"""
    sample_input = ""
    sample_output = ""
    reference_solution = ""
    test_cases = ""
    
    # 获取样例输入输出
    line = f"对于编程题目：{question}，请提供样例输入和输出，格式为：'输入：xxx 输出：xxx'，如果题目中没有明确说明，请根据题意设计合适的样例"
    io_info = aiapi("", line)
    
    # 解析样例输入输出
    if '输入：' in io_info and '输出：' in io_info:
        sample_input = io_info.split('输入：')[1].split('输出：')[0].strip()
        sample_output = io_info.split('输出：')[1].strip()
    
    # 获取测试用例
    line = f"对于编程题目：{question}，请提供3组测试用例，每组格式为：'输入：xxx 输出：xxx'，确保测试用例能覆盖不同情况"
    test_cases = aiapi("", line)
    
    # 获取参考解答
    line = f"对于编程题目：{question}，请提供Python语言的参考解答代码，不需要解释"
    reference_solution = aiapi("", line)
    
    return {
        'question_text': question,
        'sample_input': sample_input,
        'sample_output': sample_output,
        'reference_solution': reference_solution,
        'test_cases': test_cases,
        'time_limit': 1000,  # 默认1000ms
        'memory_limit': 256,  # 默认256MB
        'score': 10,         # 默认10分
        'difficulty': 3      # 默认中等难度
    }


def insert_into_db(question_info):
    """将编程题插入数据库"""
    conn = sqlite3.connect('../../database/It_g.db')
    cursor = conn.cursor()

    # 插入数据到programming_questions表
    cursor.execute('''
        INSERT INTO programming_questions 
        (subject, question_text, sample_input, sample_output, 
         reference_solution, test_cases, time_limit, memory_limit, 
         score, difficulty, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    ''', (
        'python',
        question_info['question_text'],
        question_info['sample_input'],
        question_info['sample_output'],
        question_info['reference_solution'],
        question_info['test_cases'],
        question_info['time_limit'],
        question_info['memory_limit'],
        question_info['score'],
        question_info['difficulty']
    ))

    conn.commit()
    conn.close()

