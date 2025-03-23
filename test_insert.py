import base64
from datetime import datetime, timedelta
from functools import wraps
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, flash
from docx import Document
import sqlite3
from sqlite3 import Error
from werkzeug.utils import secure_filename
import time
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from openpyxl import Workbook
from docx.shared import Inches
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.comments import Comment
import zipfile
import shutil
import logging
from split_and_ocr.pdf_ocr import process_pdf
import json
from split_and_ocr.slip import split_columns_and_rows
import re
from flask_login import LoginManager, login_user, login_required as flask_login_required, current_user, logout_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string
import csv
import pypdf
import uuid
import sys

def get_db_connection():
    """获取数据库连接"""
    # 确保数据库目录存在
    db_dir = 'database'
    os.makedirs(db_dir, exist_ok=True)

    # 构建数据库文件的绝对路径
    db_path = os.path.join(os.path.abspath(db_dir), 'It_g.db')

    max_attempts = 3
    attempt = 0
    while attempt < max_attempts:
        try:
            conn = sqlite3.connect(db_path, timeout=20)
            conn.row_factory = sqlite3.Row



            return conn
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                attempt += 1
                if attempt < max_attempts:
                    print(f"数据库被锁定，正在重试... (尝试 {attempt}/{max_attempts})")
                    time.sleep(1)  # 等待1秒后重试
                    continue
            print(f"数据库连接错误: {e}")
            return None
        except Exception as e:
            print(f"数据库连接错误: {e}")
            return None
    return None


def execute_query(query, params=None):
    """执行SQL查询"""
    conn = get_db_connection()
    if not conn:
        print("数据库连接失败")
        return False, None

    cursor = None
    result = None
    try:
        cursor = conn.cursor()
        cursor.execute(query, params or ())

        if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            conn.commit()
            result = cursor.lastrowid
        else:
            result = cursor.fetchall()
        return True, result
    except Error as e:
        print(f"SQL执行错误: {e}")
        print(f"错误的查询: {query}")
        print(f"参数: {params}")
        import traceback
        traceback.print_exc()  # 打印完整的错误堆栈
        if conn:
            conn.rollback()
        return False, None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# 添加额外的调试信息
stats_query = """
    WITH student_scores AS (
        SELECT 
            student_id,
            SUM(COALESCE(final_score, ai_score, 0)) as total_score
        FROM student_answers 
        WHERE session_id = ?
        GROUP BY student_id
    ),
    class_scores AS (
        SELECT 
            student_id,
            total_score
        FROM student_scores
    )
    SELECT 
        cs1.student_id,
        COUNT(DISTINCT cs2.student_id) + 1 as rank
    FROM class_scores cs1
    LEFT JOIN class_scores cs2 ON cs2.total_score > cs1.total_score
    WHERE cs1.student_id = ?
    GROUP BY cs1.student_id
"""
success, stats_data = execute_query(stats_query, (2,3))
print("调试查询结果:")
print(f"查询成功: {success}")
if success:
    student_score = stats_data[0]['rank']
    print(student_score)
print("测试数据添加完成！") 