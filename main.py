import base64
from datetime import datetime, timedelta
from functools import wraps
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
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

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 定义上传文件夹和解压文件夹路径
UPLOAD_FOLDER = 'uploads'
EXTRACT_FOLDER = 'extracted_files'

# 定义允许的文件类型
ALLOWED_EXTENSIONS = {'pdf', 'zip', 'rar'}

# 确保上传和解压目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXTRACT_FOLDER, exist_ok=True)

class CustomReloader:
    def should_reload(self, filename):
        # 忽略某些目录的文件变化
        ignore_dirs = [
            'uploads',
            'temp_images',
            'read',
            '__pycache__',
            '.git',
            'venv',
            'env'
        ]
        
        # 检查文件是否在忽略目录中
        for ignore_dir in ignore_dirs:
            if ignore_dir in filename:
                return False
                
        return super().should_reload(filename)

def create_app():
    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit
    
    # 设置session密钥
    app.secret_key = 'your-secret-key'  
    
    # 禁用文件更改自动重载
    app.config['DEBUG'] = True
    app.config['TEMPLATES_AUTO_RELOAD'] = False
    
    return app

app = create_app()

# 添加额外的配置来忽略特定目录
def should_ignore_file(filename):
    ignore_dirs = {UPLOAD_FOLDER, EXTRACT_FOLDER}
    return any(dir_name in filename for dir_name in ignore_dirs)

# 修改 Flask 的 reloader
extra_files = None
if app.debug:
    extra_files = [f for f in app.static_folder if not should_ignore_file(f)]

app.secret_key = 'syh2031.'

# 允许的文件类型定义
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}
ALLOWED_DOC_EXTENSIONS = {'doc', 'docx'}
ALLOWED_ZIP_EXTENSIONS = {'zip'}

def calculate_duration(start_time, end_time):
    """计算考试时长"""
    try:
        # 将字符串转换为 datetime 对象
        if isinstance(start_time, str):
            start = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        else:
            start = start_time
            
        if isinstance(end_time, str):
            end = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
        else:
            end = end_time
        
        # 计算时间差
        duration = end - start
        
        # 转换为小时和分钟
        total_minutes = duration.total_seconds() / 60
        hours = int(total_minutes // 60)
        minutes = int(total_minutes % 60)
        
        # 格式化输出
        if hours > 0:
            if minutes > 0:
                return f"{hours}小时{minutes}分钟"
            return f"{hours}小时"
        return f"{minutes}分钟"
        
    except Exception as e:
        print(f"计算时长出错: {e}")
        return "时长未知"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 添加登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'email' not in session:
            return redirect(url_for('index_login'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def index_login():
    if 'email' in session:
        return redirect(url_for('xinzeng'))
    return render_template('login.html')


@app.route('/register')
def register_page():
    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    if 'email' in session:
        return redirect(url_for('xinzeng'))
    else:
        return redirect(url_for('index_login'))


@app.route('/review')
def review():
    if 'email' in session:
        return render_template('review.html')
    else:
        return redirect(url_for('index_login'))


@app.route('/xinzeng')
def xinzeng():
    if 'email' in session:
        return render_template('xinzeng.html')
    else:
        return redirect(url_for('index_login'))


@app.route('/user')
def user():
    if 'email' in session:
        return render_template('user.html')
    else:
        return redirect(url_for('index_login'))


@app.route('/analysis')
def analysis():
    if 'email' in session:
        return render_template('analysis.html')
    else:
        return redirect(url_for('index_login'))


@app.route('/exam')
def exam():
    if 'email' in session:
        return render_template('exam.html')
    else:
        return redirect(url_for('index_login'))


@app.route('/index')
def index():
    if 'email' in session:
        return render_template('index.html')
    else:
        return redirect(url_for('index_login'))


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
            
            # 初始化数据库表（如果不存在）
            init_database(conn)
            
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

def init_database(conn):
    """初始化数据库表"""
    try:
        cursor = conn.cursor()
        
        # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建考试场次表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exam_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                duration INTEGER NOT NULL,
                exam_file_path TEXT NOT NULL,
                exam_score REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建学生表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                student_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建题目表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                question_type TEXT NOT NULL,  -- 新增：题目类型
                question_text TEXT NOT NULL,
                score INTEGER NOT NULL,
                question_order INTEGER NOT NULL,
                source_question_id INTEGER,   -- 新增：关联原题库的ID
                source_table TEXT,           -- 新增：来源题库表名
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES exam_sessions (id)
            )
        ''')
        
        # 创建学生答案表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                question_type TEXT NOT NULL,
                answer_text TEXT,
                ai_score REAL,
                ai_feedback TEXT,
                scoring_details TEXT,        -- JSON格式存储评分细节
                review_status TEXT DEFAULT 'pending',
                reviewed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES exam_sessions(id),
                FOREIGN KEY (student_id) REFERENCES students(id),
                FOREIGN KEY (question_id) REFERENCES questions(id)
            )
        ''')
        
        # 创建题目分析表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS question_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                average_score_rate REAL NOT NULL,
                difficulty_coefficient REAL NOT NULL,
                discrimination_degree REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES exam_sessions (id),
                FOREIGN KEY (question_id) REFERENCES questions (id)
            )
        ''')
        
        # 创建操作日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                operation_type TEXT NOT NULL,
                operation_details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # 创建导出日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS export_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                export_type TEXT NOT NULL,
                report_type TEXT NOT NULL,
                format_type TEXT NOT NULL,
                session_id INTEGER,
                student_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (session_id) REFERENCES exam_sessions (id),
                FOREIGN KEY (student_id) REFERENCES students (id)
            )
        ''')
        
        # 以选择题为例
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS multiple_choice_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                question_text TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                explanation TEXT,            -- 新增：解析
                score INTEGER NOT NULL,
                difficulty INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_template BOOLEAN DEFAULT TRUE  -- 新增：标记是否为题库模板
            )
        ''')
        
        conn.commit()
    except Exception as e:
        print(f"初始化数据库失败: {e}")
        conn.rollback()
        raise e

def execute_query(query, params=None):
    """执行SQL查询"""
    conn = get_db_connection()
    if not conn:
        return None, None
    
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
        if conn:
            conn.rollback()
        return False, None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    pwd = request.form.get('password')

    # 使用参数化查询防止SQL注入
    query = "SELECT * FROM users WHERE email = ?"
    success, result = execute_query(query, (email,))
    
    if not success:
        return '数据库错误 <a href="/">返回登录</a>'
    
    if result and len(result) > 0:
        user = result[0]
        if pwd == user['password']:  # 实际应用中应使用密码哈希
            session["email"] = email
            
            # 记录登录操作
            log_query = """
                INSERT INTO operation_logs (user_id, operation_type, operation_details) 
                VALUES (?, ?, ?)
            """
            execute_query(log_query, (user['id'], 'login', f'User logged in from {request.remote_addr}'))
            
            return redirect(url_for('xinzeng'))
        else:
            return '密码错误 <a href="/">返回登录</a>'
    else:
        return '用户名不存在 <a href="/">返回登录</a>'

@app.route('/register', methods=['POST'])
def register():
    email = request.form.get('email')
    pwd = request.form.get('password')
    pwd2 = request.form.get('confirm_password')
    
    if pwd != pwd2:
        return '两次密码不一致 <a href="/register">返回注册</a>'
    
    # 检查用户是否已存在
    check_query = "SELECT * FROM users WHERE email = ?"
    success, result = execute_query(check_query, (email,))
    
    if not success:
        return '数据库错误 <a href="/register">返回注册</a>'
    
    if result and len(result) > 0:
        return '用户名已存在 <a href="/register">返回注册</a>'
    
    # 创建新用户
    insert_query = "INSERT INTO users (email, password) VALUES (?, ?)"
    success, user_id = execute_query(insert_query, (email, pwd))
    
    if success:
        # 记录注册操作
        log_query = """
            INSERT INTO operation_logs (user_id, operation_type, operation_details) 
            VALUES (?, ?, ?)
        """
        execute_query(log_query, (user_id, 'register', f'New user registration from {request.remote_addr}'))
        
        return '注册成功 <a href="/">返回登录</a>'
    else:
        return '注册失败 <a href="/register">返回注册</a>'

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('index_login'))

def sanitize_filename(filename):
    """处理文件名，保留中文字符"""
    # 替换不安全的字符
    unsafe_chars = '/\\?%*:|"<>'
    filename = ''.join(c if c not in unsafe_chars else '_' for c in filename)
    return filename.strip('.')

@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传请求"""
    try:
        # 检查是否有文件被上传
        if not request.files:
            logger.warning('没有文件被上传')
            return jsonify({'error': '没有文件被上传'}), 400
            
        file_type = request.form.get('type', '')  # 'image' 或 'document'
        if not file_type:
            logger.warning('未指定文件类型')
            return jsonify({'error': '未指定文件类型'}), 400
            
        # 为此次上传创建唯一的目录
        timestamp = str(int(time.time()))
        extract_dir = os.path.join(EXTRACT_FOLDER, timestamp)
        os.makedirs(extract_dir, exist_ok=True)
        logger.info(f'创建上传目录: {extract_dir}')
        
        files_info = []
        temp_files = []  # 用于跟踪需要清理的临时文件
        
        # 处理所有上传的文件
        for key in request.files:
            file = request.files[key]
            if file.filename == '':
                continue
                
            # 处理文件名，确保中文文件名也能正常工作
            original_filename = file.filename
            # 使用自定义的文件名清理函数
            filename = sanitize_filename(original_filename)
            if filename == '':  # 如果文件名为空
                filename = f"{str(int(time.time()))}_{key}"  # 使用时间戳作为文件名
                
            if '.' not in filename:
                logger.warning(f'无效的文件名: {original_filename}')
                continue
                
            file_ext = filename.rsplit('.', 1)[1].lower()
            logger.info(f'处理文件: {filename} (类型: {file_ext})')
            
            # 检查文件类型
            if file_type == 'image':
                if file_ext not in ALLOWED_IMAGE_EXTENSIONS and file_ext not in ALLOWED_ZIP_EXTENSIONS:
                    logger.warning(f'不支持的图片文件类型: {file_ext}')
                    continue
            elif file_type == 'document':
                if file_ext not in ALLOWED_DOC_EXTENSIONS and file_ext not in ALLOWED_ZIP_EXTENSIONS:
                    logger.warning(f'不支持的文档文件类型: {file_ext}')
                    continue
            else:
                logger.error(f'无效的文件类型: {file_type}')
                return jsonify({'error': '无效的文件类型'}), 400
                
            # 保存文件
            file_path = os.path.join(extract_dir, filename)
            file.save(file_path)
            temp_files.append(file_path)
            logger.info(f'文件已保存: {file_path}')
            
            # 如果是压缩包，解压处理
            if file_ext in ALLOWED_ZIP_EXTENSIONS:
                zip_ref = None
                try:
                    zip_ref = zipfile.ZipFile(file_path, 'r', allowZip64=True)
                    # 创建子目录用于解压文件
                    zip_extract_dir = os.path.join(extract_dir, os.path.splitext(filename)[0])
                    os.makedirs(zip_extract_dir, exist_ok=True)
                    
                    # 获取压缩包中的所有文件
                    for zip_info in zip_ref.filelist:
                        try:
                            # 尝试不同的编码方式
                            try:
                                # 首先尝试 UTF-8
                                name = zip_info.filename.encode('cp437').decode('utf-8')
                            except UnicodeDecodeError:
                                try:
                                    # 然后尝试 GBK
                                    name = zip_info.filename.encode('cp437').decode('gbk')
                                except UnicodeDecodeError:
                                    # 如果都失败，保持原样
                                    name = zip_info.filename
                            
                            # 清理文件名
                            clean_name = sanitize_filename(name)
                            
                            # 如果是目录，创建它
                            if zip_info.filename.endswith('/'):
                                target_dir = os.path.join(zip_extract_dir, clean_name)
                                os.makedirs(target_dir, exist_ok=True)
                                continue
                            
                            # 提取文件
                            source = None
                            target = None
                            try:
                                source = zip_ref.open(zip_info)
                                target_path = os.path.join(zip_extract_dir, clean_name)
                                
                                # 确保目标目录存在
                                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                                
                                with open(target_path, 'wb') as target:
                                    shutil.copyfileobj(source, target)
                            finally:
                                # 确保文件句柄被关闭
                                if source:
                                    source.close()
                            
                        except Exception as e:
                            logger.error(f'处理压缩文件 {zip_info.filename} 时出错: {str(e)}')
                            continue
                    
                    logger.info(f'解压文件成功: {file_path} 到 {zip_extract_dir}')
                    
                    # 获取解压后的文件列表
                    for root, _, files in os.walk(zip_extract_dir):
                        for f in files:
                            try:
                                f_ext = f.rsplit('.', 1)[1].lower() if '.' in f else ''
                                if ((file_type == 'image' and f_ext in ALLOWED_IMAGE_EXTENSIONS) or
                                    (file_type == 'document' and f_ext in ALLOWED_DOC_EXTENSIONS)):
                                    file_path = os.path.join(root, f)
                                    relative_path = os.path.relpath(file_path, extract_dir)
                                    files_info.append({
                                        'name': f,
                                        'path': relative_path,
                                        'original_name': f  # 使用解压后的文件名作为原始名称
                                    })
                                    logger.info(f'处理解压文件: {relative_path}')
                            except Exception as e:
                                logger.error(f'处理解压后的文件 {f} 时出错: {str(e)}')
                                continue
                
                except Exception as e:
                    logger.error(f'解压文件出错: {str(e)}')
                    # 如果解压失败，将zip文件作为普通文件处理
                    files_info.append({
                        'name': filename,
                        'path': filename,
                        'original_name': original_filename
                    })
                
                finally:
                    # 确保zip文件被关闭
                    if zip_ref:
                        zip_ref.close()
                    
                    # 等待一小段时间确保文件句柄被释放
                    time.sleep(0.1)
                    
                    # 删除原始压缩包
                    try:
                        if os.path.exists(temp_files[-1]):
                            os.remove(temp_files[-1])  # 删除最后添加的文件（压缩包）
                            temp_files.pop()  # 从临时文件列表中移除
                            logger.info(f'删除原始压缩包: {file_path}')
                    except Exception as e:
                        logger.error(f'删除压缩包失败: {str(e)}')
                        # 如果删除失败，将在后续清理中处理
            else:
                # 处理普通文件
                files_info.append({
                    'name': filename,
                    'path': filename,
                    'original_name': original_filename
                })
        
        if not files_info:
            logger.warning('没有有效的文件被上传')
            # 清理所有临时文件
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.info(f'清理临时文件: {temp_file}')
                except Exception as e:
                    logger.error(f'清理文件失败: {temp_file} - {str(e)}')
            return jsonify({'error': '没有有效的文件被上传'}), 400
            
        logger.info(f'文件上传成功: {len(files_info)} 个文件')
        return jsonify({
            'message': '文件上传成功',
            'extract_dir': timestamp,
            'files': files_info,
            'type': file_type
        })
        
    except Exception as e:
        logger.error(f'文件上传错误: {str(e)}')
        # 清理临时文件
        if 'extract_dir' in locals() and os.path.exists(extract_dir):
            try:
                shutil.rmtree(extract_dir)
                logger.info(f'清理临时目录: {extract_dir}')
            except Exception as cleanup_error:
                logger.error(f'清理临时目录失败: {str(cleanup_error)}')
        return jsonify({'error': f'处理文件时出错: {str(e)}'}), 500

@app.route('/upload-word', methods=['POST'])
def upload_word_file():
    """处理Word文档上传请求"""
    if 'file' not in request.files:
        return jsonify({'error': '没有文件被上传'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
        
    try:
        filename = secure_filename(file.filename)
        file_ext = filename.rsplit('.', 1)[1].lower()
        
        # 检查是否是Word文档或ZIP文件
        if file_ext not in ALLOWED_DOC_EXTENSIONS and file_ext not in ALLOWED_ZIP_EXTENSIONS:
            return jsonify({'error': '不支持的文件类型'}), 400
            
        # 为此次上传创建唯一的目录
        extract_dir = os.path.join(EXTRACT_FOLDER, str(int(time.time())))
        os.makedirs(extract_dir, exist_ok=True)
        
        files_info = []
        
        # 处理ZIP文件
        if file_ext in ALLOWED_ZIP_EXTENSIONS:
            zip_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(zip_path)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
                
            # 处理解压出的Word文档
            for root, _, files in os.walk(extract_dir):
                for f in files:
                    if f.lower().endswith(tuple(ALLOWED_DOC_EXTENSIONS)):
                        doc_path = os.path.join(root, f)
                        # 读取Word文档内容
                        doc = Document(doc_path)
                        # 提取文本
                        text = "\n".join([para.text for para in doc.paragraphs])
                        # 保存为txt文件
                        txt_filename = f"{os.path.splitext(f)[0]}.txt"
                        txt_path = os.path.join(root, txt_filename)
                        with open(txt_path, 'w', encoding='utf-8') as txt_file:
                            txt_file.write(text)
                        
                        relative_path = os.path.relpath(txt_path, extract_dir)
                        files_info.append({
                            'name': txt_filename,
                            'path': relative_path,
                            'original': f
                        })
            
            os.remove(zip_path)  # 删除原始压缩包
            
        # 处理单个Word文档
        else:
            file_path = os.path.join(extract_dir, filename)
            file.save(file_path)
            
            # 读取Word文档内容
            doc = Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            
            # 保存为txt文件
            txt_filename = f"{os.path.splitext(filename)[0]}.txt"
            txt_path = os.path.join(extract_dir, txt_filename)
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(text)
                
            files_info.append({
                'name': txt_filename,
                'path': txt_filename,
                'original': filename
            })
            
            # 可以选择是否保留原始Word文件
            os.remove(file_path)
        
        return jsonify({
            'message': '文件处理成功',
            'extract_dir': os.path.basename(extract_dir),
            'files': files_info
        })
        
    except Exception as e:
        # 清理临时文件
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        return jsonify({'error': f'处理文件时出错: {str(e)}'}), 500

@app.route('/exam/list')
@login_required
def exam_list():
    # 获取当前时间
    now = datetime.now()

    # 模拟从数据库获取考试数据
    exams = [
        {
            'id': 1,
            'name': '2024年春季期中考试 - 人工智能基础',
            'subject': '人工智能基础',
            'duration': 120,
            'total_score': 100,
            'start_time': datetime(2024, 4, 15, 9, 0),
            'end_time': datetime(2024, 4, 15, 11, 0),
            'status': 'ongoing',  # ongoing, upcoming, completed
            'score': None
        },
        {
            'id': 2,
            'name': '2024年春季期末考试 - 人工智能基础',
            'subject': '人工智能基础',
            'duration': 120,
            'total_score': 100,
            'start_time': datetime(2024, 6, 15, 9, 0),
            'end_time': datetime(2024, 6, 15, 11, 0),
            'status': 'upcoming',
            'score': None
        },
        {
            'id': 3,
            'name': '2023年秋季期末考试 - 人工智能基础',
            'subject': '人工智能基础',
            'duration': 120,
            'total_score': 100,
            'start_time': datetime(2023, 12, 15, 9, 0),
            'end_time': datetime(2023, 12, 15, 11, 0),
            'status': 'completed',
            'score': 95
        }
    ]

    return render_template('exam_list.html', exams=exams)


@app.route('/exam/<int:exam_id>/detail')
@login_required
def exam_detail(exam_id):
    # 获取考试详情
    exam = {
        'id': exam_id,
        'name': '2023年秋季期末考试 - 人工智能基础',
        'duration': 120,
        'total_score': 100,
        'score': 95,
        'start_time': datetime(2023, 12, 15, 9, 0),
        'questions': {
            'multiple_choice': [
                {
                    'question': '下列关于人工智能的说法，正确的是：',
                    'options': [
                        '人工智能只能处理数值计算',
                        '机器学习是人工智能的一个子领域',
                        '深度学习不属于机器学习范畴',
                        '人工智能必须具备自主意识'
                    ],
                    'correct_answer': 1,  # B是正确答案
                    'user_answer': 1,
                    'score': 5
                }
            ],
            'fill_blanks': [
                {
                    'question': '机器学习主要分为监督学习、_____和强化学习三种类型。',
                    'correct_answer': '无监督学习',
                    'user_answer': '无监督学习',
                    'is_correct': True,
                    'score': 10
                }
            ],
            'short_answer': [
                {
                    'question': '请详细解释人工智能的基本概念，包括其定义、特点和应用领域。',
                    'user_answer': '人工智能是计算机科学的一个分支，它试图理解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器...',
                    'feedback': '答案完整，论述清晰，举例恰当。建议可以补充更多实际应用案例。',
                    'score': 23
                }
            ]
        }
    }

    return render_template('exam_detail.html', exam=exam, chr=chr)


@app.route('/exam/<int:exam_id>/save', methods=['POST'])
@login_required
def save_exam_answers(exam_id):
    data = request.get_json()

    try:
        # 保存答案到数据库
        save_answers_to_db(current_user.id, exam_id, data['answers'])
        return jsonify({'status': 'success', 'message': '保存成功'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/exam/<int:exam_id>/submit', methods=['POST'])
@login_required
def submit_exam(exam_id):
    data = request.get_json()

    try:
        # 检查是否在考试时间内
        exam = get_exam_by_id(exam_id)
        now = datetime.now()
        if now > exam['end_time']:
            return jsonify({'status': 'error', 'message': '考试已结束，无法提交'}), 400

        # 保存最终答案
        save_answers_to_db(current_user.id, exam_id, data['answers'])

        # 标记考试为已完成
        mark_exam_completed(current_user.id, exam_id)

        # 返回成功消息
        return jsonify({
            'status': 'success',
            'message': '试卷提交成功',
            'redirect': url_for('exam_list')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


def get_exam_by_id(exam_id):
    # 模拟从数据库获取考试信息
    exams = {
        1: {
            'id': 1,
            'name': '2024年春季期中考试 - 人工智能基础',
            'subject': '人工智能基础',
            'duration': 120,
            'total_score': 100,
            'start_time': datetime(2024, 4, 15, 9, 0),
            'end_time': datetime(2024, 4, 15, 11, 0)
        }
    }
    return exams.get(exam_id)


def get_exam_questions(exam_id):
    # 模拟从数据库获取试题
    return {
        'multiple_choice': [
            {
                'id': 1,
                'question': '下列关于人工智能的说法，正确的是：',
                'options': [
                    'A. 人工智能只能处理数值计算',
                    'B. 机器学习是人工智能的一个子领域',
                    'C. 深度学习不属于机器学习范畴',
                    'D. 人工智能必须具备自主意识'
                ],
                'score': 5
            }
        ],
        'fill_blanks': [
            {
                'id': 1,
                'question': '机器学习主要分为监督学习、_____和强化学习三种类型。',
                'score': 10
            }
        ],
        'short_answer': [
            {
                'id': 1,
                'question': '请详细解释人工智能的基本概念，包括其定义、特点和应用领域。',
                'score': 25
            }
        ]
    }


def has_taken_exam(user_id, exam_id):
    # 检查用户是否已参加过考试
    # 实际应用中需要查询数据库
    return False


def save_answers_to_db(user_id, exam_id, answers):
    # 保存答案到数据库
    # 实际应用中需要实现数据库操作
    pass


def mark_exam_completed(user_id, exam_id):
    # 标记考试为已完成
    # 实际应用中需要实现数据库操作
    pass

@app.route('/api/sessions', methods=['GET'])
@login_required
def get_exam_sessions():
    """获取所有考试场次"""
    search_term = request.args.get('search', '').strip()
    
    if search_term:
        query = """
            SELECT id, name, subject, start_time, end_time, status 
            FROM exam_sessions 
            WHERE name LIKE ?  
            ORDER BY start_time DESC
        """
        search_param = f'%{search_term}%'
        success, sessions = execute_query(query, (search_param,))
    else:
        # 如果没有搜索词，返回所有考试场次
        query = """
            SELECT id, name, subject, start_time, end_time, status 
            FROM exam_sessions 
            ORDER BY start_time DESC
        """
        success, sessions = execute_query(query)
    
    if not success:
        return jsonify({'error': '获取考试场次失败'}), 500
    
    # 确保返回的是列表
    sessions = sessions if sessions else []
    
    # 格式化日期时间
    formatted_sessions = []
    for session in sessions:
        try:
            # 处理日期时间字段
            start_time = datetime.strptime(session['start_time'], '%Y-%m-%d %H:%M:%S.%f') if '.' in session['start_time'] else datetime.strptime(session['start_time'], '%Y-%m-%d %H:%M:%S')
            end_time = datetime.strptime(session['end_time'], '%Y-%m-%d %H:%M:%S.%f') if '.' in session['end_time'] else datetime.strptime(session['end_time'], '%Y-%m-%d %H:%M:%S')
            
            formatted_session = {
                'id': session['id'],
                'name': session['name'],
                'subject': session['subject'],
                'start_time': start_time.strftime('%Y-%m-%d %H:%M'),
                'end_time': end_time.strftime('%Y-%m-%d %H:%M'),
                'status': session['status']
            }
            formatted_sessions.append(formatted_session)
        except Exception as e:
            print(f"格式化会话数据时出错: {str(e)}")
            continue
    
    return jsonify(formatted_sessions)

@app.route('/api/session/<int:session_id>', methods=['DELETE'])
@login_required
def delete_exam_session(session_id):
    """删除指定的考试场次"""
    try:
        # 直接执行删除操作
        query = "DELETE FROM exam_sessions WHERE id = ?"
        success, _ = execute_query(query, (session_id,))
        
        if not success:
            print(f"删除失败: session_id={session_id}")
            return jsonify({'error': '删除考试场次失败'}), 500
            
        return jsonify({'message': '删除成功'})
    except Exception as e:
        print(f"删除考试场次错误: {str(e)}")
        return jsonify({'error': '删除考试场次失败'}), 500

@app.route('/api/session', methods=['POST'])
@login_required
def create_exam_session():
    try:
        # 获取表单数据
        name = request.form.get('name')
        subject = request.form.get('subject')
        exam_time = request.form.get('examTime')
        duration = request.form.get('duration')
        exam_file = request.files.get('examFile')
        
        if not exam_file:
            return jsonify({'error': '未上传试卷文件'}), 400
            
        # 确保上传目录存在
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # 保存试卷文件
        exam_filename = secure_filename(f"{name}_exam_{exam_file.filename}")
        exam_path = os.path.join(UPLOAD_FOLDER, exam_filename)
        exam_file.save(exam_path)
        
        try:
            # 处理试卷PDF
            print("开始处理试卷PDF...")
            exam_score = process_pdf(exam_path, out_input="oocr_results.txt")
            
            if exam_score == 0:
                if os.path.exists(exam_path):
                    os.remove(exam_path)
                return jsonify({'error': '试卷PDF处理失败'}), 500
            
            # 处理时间
            exam_datetime = datetime.strptime(exam_time, '%Y-%m-%dT%H:%M')
            end_datetime = exam_datetime + timedelta(minutes=int(duration))
            
            # 获取当前用户ID
            user_id = get_current_user_id()
            if not user_id:
                raise Exception('未获取到用户信息')
            
            # 连接数据库
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 插入考试信息
            cursor.execute('''
                INSERT INTO exam_sessions (name, subject, start_time, end_time, duration, exam_file_path, exam_score, status, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, subject, exam_datetime, end_datetime, duration, exam_path, exam_score, 'pending', user_id))
            
            # 提交更改
            conn.commit()
            conn.close()
            from split_and_ocr.read.aiexam import AIExam
            AIExam.run_ocr()
            return jsonify({'message': '考试创建成功'}), 200
            
        except Exception as e:
            # 如果处理过程中出现错误，删除已上传的文件
            if os.path.exists(exam_path):
                os.remove(exam_path)
            raise e
            
    except Exception as e:
        print(f"创建考试失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/exam-sessions', methods=['GET'])
@login_required
def get_exam_sessions_index():
    """获取所有考试场次"""
    query = """
        SELECT id, name as session_name 
        FROM exam_sessions 
        WHERE status != 'completed'
        ORDER BY start_time ASC
    """
    
    success, sessions = execute_query(query)
    
    if not success:
        return jsonify({'error': '获取考试场次失败'}), 500
    
    # 确保返回的是列表
    sessions = [dict(session) for session in sessions] if sessions else []
    
    return jsonify(sessions)

@app.route('/api/review/sessions', methods=['GET'])
@login_required
def get_review_sessions():
    """获取需要复核的考试场次"""
    query = """
        SELECT 
            es.id,
            es.name,
            es.subject,
            es.start_time,
            es.end_time
        FROM exam_sessions es
    """
    
    print("Executing sessions query")  # 调试日志
    success, sessions = execute_query(query)
    print(f"Sessions result: {sessions}")  # 调试日志
    
    if not success:
        print("Failed to get sessions")  # 调试日志
        return jsonify({'error': '获取考试场次失败'}), 500
        
    return jsonify([dict(session) for session in (sessions or [])])

@app.route('/api/review/students/<int:session_id>', methods=['GET'])
@login_required
def get_session_students(session_id):
    """获取指定考试场次的学生列表"""
    search = request.args.get('search', '').strip()
    
    query = """
        SELECT DISTINCT
            s.id,
            s.name,
            s.student_id,
            SUM(sa.ai_score) as initial_score,
            MIN(sa.review_status) as review_status
        FROM students s
        JOIN student_answers sa ON s.id = sa.student_id
        WHERE sa.session_id = ?
        GROUP BY s.id, s.name, s.student_id
    """
    
    params = [session_id]
    
    if search:
        query = """
            SELECT DISTINCT
                s.id,
                s.name,
                s.student_id,
                SUM(sa.ai_score) as initial_score,
                MIN(sa.review_status) as review_status
            FROM students s
            JOIN student_answers sa ON s.id = sa.student_id
            WHERE sa.session_id = ?
            AND (s.name LIKE ? OR s.student_id LIKE ?)
            GROUP BY s.id, s.name, s.student_id
        """
        params.extend([f'%{search}%', f'%{search}%'])
    
    print(f"Executing query: {query}")
    print(f"With params: {params}")
    
    success, students = execute_query(query, params)
    
    if not success:
        print("Query failed")
        return jsonify({'error': '获取学生列表失败'}), 500
    
    print(f"Query results: {students}")
    
    return jsonify([{
        'id': student['id'],
        'name': student['name'],
        'student_id': student['student_id'],
        'initial_score': student['initial_score'] or 0,
        'review_status': student['review_status'] or 'pending'
    } for student in (students or [])])

@app.route('/api/review/answers/<int:session_id>/<int:student_id>', methods=['GET'])
@login_required
def get_student_answers(session_id, student_id):
    """获取学生的答题详情"""
    print(f"Getting answers for session {session_id}, student {student_id}")  # 调试日志
    
    query = """
        SELECT 
            q.id as question_id,
            q.question_text,
            q.score as total_score,
            q.question_order,
            sa.answer_text,
            sa.ai_score,
            sa.ai_feedback,
            sa.review_status
        FROM questions q
        JOIN student_answers sa ON q.id = sa.question_id
        WHERE sa.session_id = ? AND sa.student_id = ?
        ORDER BY q.question_order
    """
    
    success, answers = execute_query(query, (session_id, student_id))
    print(f"Query results: {answers}")  # 调试日志
    
    if not success:
        print("Query failed")  # 调试日志
        return jsonify({'error': '获取答题详情失败'}), 500
        
    result = [{
        'question_id': answer['question_id'],
        'question_text': answer['question_text'],
        'total_score': answer['total_score'],
        'question_order': answer['question_order'],
        'answer_text': answer['answer_text'],
        'ai_score': answer['ai_score'],
        'ai_feedback': answer['ai_feedback'],
        'review_status': answer['review_status'] or 'pending'
    } for answer in (answers or [])]
    
    print(f"Returning: {result}")  # 调试日志
    return jsonify(result)

@app.route('/api/review/submit', methods=['POST'])
@login_required
def submit_review():
    """提交人工复核结果"""
    data = request.get_json()
    session_id = data.get('session_id')
    student_id = data.get('student_id')
    question_id = data.get('question_id')
    final_score = data.get('final_score')
    
    if not all([session_id, student_id, question_id, final_score is not None]):
        return jsonify({'error': '缺少必要参数'}), 400
        
    update_query = """
        UPDATE student_answers
        SET final_score = ?,
            review_status = 'reviewed',
            reviewed_at = CURRENT_TIMESTAMP
        WHERE session_id = ? AND student_id = ? AND question_id = ?
    """
    
    success, _ = execute_query(update_query, (final_score, session_id, student_id, question_id))
    
    if not success:
        return jsonify({'error': '保存复核结果失败'}), 500
        
    return jsonify({'message': '复核结果已保存'})

@app.route('/api/review/batch', methods=['POST'])
@login_required
def batch_review():
    """批量复核"""
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'error': '缺少考试场次ID'}), 400
        
    # 获取所有未复核的答卷
    query = """
        UPDATE student_answers
        SET final_score = ai_score,
            review_status = 'reviewed',
            reviewed_at = CURRENT_TIMESTAMP
        WHERE session_id = ? AND review_status = 'pending'
    """
    
    success, _ = execute_query(query, (session_id,))
    
    if not success:
        return jsonify({'error': '批量复核失败'}), 500
        
    return jsonify({'message': '批量复核完成'})

# 获取考试场次列表
@app.route('/api/analysis/sessions')
@login_required
def get_analysis_sessions():
    """获取所有已完成的考试场次"""
    query = """
        SELECT 
            id,
            name,
            subject,
            start_time,
            end_time,
            status
        FROM exam_sessions 
        WHERE status IN ('completed', 'graded')
        ORDER BY start_time DESC
    """
    
    print("执行考试场次查询")  # 调试日志
    success, sessions = execute_query(query)
    print(f"查询结果: success={success}, sessions={sessions}")  # 调试日志
    
    if not success:
        print("获取考试场次失败")  # 调试日志
        return jsonify([])
        
    result = [{
        'id': session['id'],
        'name': session['name'],
        'subject': session['subject'],
        'start_time': session['start_time'],
        'end_time': session['end_time']
    } for session in (sessions or [])]
    
    print(f"返回数据: {result}")  # 调试日志
    return jsonify(result)

# 获取考试场次基本统计信息
@app.route('/api/analysis/basic-stats/<int:session_id>')
@login_required
def get_basic_stats(session_id):
    """获取考试的基本统计信息"""
    query = """
        WITH student_total_scores AS (
            SELECT 
                student_id,
                SUM(COALESCE(ai_score, 0)) as total_score
            FROM student_answers
            WHERE session_id = ?
            GROUP BY student_id
        ),
        stats AS (
            SELECT 
                ROUND(AVG(CAST(total_score AS FLOAT)), 1) as average_score,
                ROUND((COUNT(CASE WHEN total_score >= 60 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)), 0) as pass_rate,
                MAX(total_score) as highest_score,
                COUNT(DISTINCT student_id) as total_students,
                COUNT(DISTINCT CASE WHEN EXISTS (
                    SELECT 1 FROM student_answers sa2 
                    WHERE sa2.student_id = student_total_scores.student_id 
                    AND sa2.session_id = ? 
                    AND sa2.ai_score IS NULL
                ) THEN student_id END) as ungraded_count
            FROM student_total_scores
        ),
        top_student AS (
            SELECT 
                s.name as student_name,
                s.student_id as student_number
            FROM student_total_scores sts
            JOIN students s ON sts.student_id = s.id
            WHERE sts.total_score = (
                SELECT MAX(total_score)
                FROM student_total_scores
            )
            LIMIT 1
        )
        SELECT 
            stats.*,
            top_student.student_name,
            top_student.student_number
        FROM stats, top_student
    """
    
    success, stats = execute_query(query, (session_id, session_id))
    
    if not success or not stats:
        return jsonify({
            'average_score': 0,
            'pass_rate': 0,
            'highest_score': 0,
            'total_students': 0,
            'ungraded_count': 0,
            'highest_score_student': {
                'name': '',
                'student_id': ''
            }
        })

    # 获取上一次考试的统计数据用于比较
    prev_query = """
        WITH prev_exam AS (
            SELECT id
            FROM exam_sessions
            WHERE start_time < (
                SELECT start_time 
                FROM exam_sessions 
                WHERE id = ?
            )
            ORDER BY start_time DESC
            LIMIT 1
        ),
        student_total_scores AS (
            SELECT 
                student_id,
                SUM(COALESCE(ai_score, 0)) as total_score
            FROM student_answers sa
            JOIN prev_exam pe ON sa.session_id = pe.id
            GROUP BY student_id
        )
        SELECT 
            ROUND(AVG(CAST(total_score AS FLOAT)), 1) as average_score,
            ROUND((COUNT(CASE WHEN total_score >= 60 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)), 0) as pass_rate
        FROM student_total_scores
    """
    
    success, prev_stats = execute_query(prev_query, (session_id,))
    
    current_stats = stats[0]
    
    # 处理没有上一次考试数据的情况
    if success and prev_stats and prev_stats[0]['average_score'] is not None:
        prev_stats = prev_stats[0]
        avg_change = round(float(current_stats['average_score']) - float(prev_stats['average_score']), 1)
        pass_rate_change = round(float(current_stats['pass_rate']) - float(prev_stats['pass_rate']), 0)
    else:
        avg_change = 0
        pass_rate_change = 0
    
    return jsonify({
        'average_score': current_stats['average_score'],
        'average_score_change': avg_change,
        'pass_rate': current_stats['pass_rate'],
        'pass_rate_change': pass_rate_change,
        'highest_score': current_stats['highest_score'],
        'total_students': current_stats['total_students'],
        'ungraded_count': current_stats['ungraded_count'],
        'highest_score_student': {
            'name': current_stats['student_name'],
            'student_id': current_stats['student_number']
        }
    })

# 获取分数分布数据
@app.route('/api/analysis/score-distribution/<int:session_id>')
@login_required
def get_score_distribution(session_id):
    """获取分数分布数据"""
    query = """
        WITH student_total_scores AS (
            SELECT 
                student_id,
                SUM(COALESCE(ai_score, 0)) as total_score,
                CASE WHEN EXISTS (
                    SELECT 1 FROM student_answers sa2 
                    WHERE sa2.student_id = sa1.student_id 
                    AND sa2.session_id = sa1.session_id 
                    AND sa2.ai_score IS NULL
                ) THEN 1 ELSE 0 END as has_ungraded
            FROM student_answers sa1
            WHERE session_id = ?
            GROUP BY student_id
        )
        SELECT 
            CASE 
                WHEN total_score >= 90 THEN '90-100'
                WHEN total_score >= 80 THEN '80-89'
                WHEN total_score >= 70 THEN '70-79'
                WHEN total_score >= 60 THEN '60-69'
                ELSE '0-59'
            END as score_range,
            COUNT(*) as student_count,
            SUM(has_ungraded) as ungraded_count
        FROM student_total_scores
        GROUP BY 
            CASE 
                WHEN total_score >= 90 THEN '90-100'
                WHEN total_score >= 80 THEN '80-89'
                WHEN total_score >= 70 THEN '70-79'
                WHEN total_score >= 60 THEN '60-69'
                ELSE '0-59'
            END
        ORDER BY score_range DESC
    """
    
    success, distribution = execute_query(query, (session_id,))
    
    if not success:
        return jsonify([])
    
    # 确保所有分数段都有数据，按照从高到低的顺序
    ranges = ['90-100', '80-89', '70-79', '60-69', '0-59']
    dist_dict = {d['score_range']: {'count': d['student_count'], 'ungraded': d['ungraded_count']} for d in (distribution or [])}
    
    result = [{
        'range': r, 
        'count': dist_dict.get(r, {'count': 0, 'ungraded': 0})['count'],
        'ungraded': dist_dict.get(r, {'count': 0, 'ungraded': 0})['ungraded']
    } for r in ranges]
    
    print(f"分数分布数据: {result}")  # 调试输出
    
    return jsonify(result)

# 获取题目分析数据
@app.route('/api/analysis/question-analysis/<int:session_id>')
@login_required
def get_question_analysis(session_id):
    """获取题目分析数据"""
    query = """
        SELECT 
            q.question_text,
            qa.average_score_rate,
            qa.difficulty_coefficient,
            qa.discrimination_degree
        FROM question_analysis qa
        JOIN questions q ON qa.question_id = q.id
        WHERE qa.session_id = ?
        ORDER BY q.question_order
    """
    success, analysis = execute_query(query, (session_id,))
    if not success or not analysis:
        return jsonify({'error': '获取题目分析失败'}), 500
    
    return jsonify([{
        'question': a['question_text'],
        'average_score_rate': a['average_score_rate'],
        'difficulty': a['difficulty_coefficient'],
        'discrimination': a['discrimination_degree']
    } for a in (analysis or [])])

# 获取学生历史成绩
@app.route('/api/analysis/student-history/<string:search_term>')
@login_required
def get_student_history(search_term):
    """获取学生的历史成绩记录"""
    try:
        print(f"搜索学生: {search_term}")  # 调试日志
        
        # 检查数据库连接
        conn = get_db_connection()
        if not conn:
            print("数据库连接失败")
            return jsonify({'error': '数据库连接失败'}), 500
            
        # 先查找学生
        student_query = """
            SELECT id, name, student_id
            FROM students
            WHERE name LIKE ? OR student_id LIKE ?
        """
        search_pattern = f"%{search_term}%"
        print(f"执行查询: {student_query} 参数: {search_pattern}")  # 调试日志
        
        success, students = execute_query(student_query, (search_pattern, search_pattern))
        print(f"查询结果: success={success}, students={students}")  # 调试日志
        
        if not success:
            return jsonify({'error': '数据库查询失败'}), 500
            
        if not students:
            return jsonify({
                'student': None,
                'history': []
            })
            
        # 检查学生数据
        student = students[0]
        print(f"找到学生: {student}")  # 调试日志
        
        # 构造返回数据
        result = {
            'student': {
                'id': student['id'],
                'name': student['name'],
                'student_id': student['student_id']
            },
            'history': []
        }
        
        # 如果找到学生，再查询历史成绩
        if result['student']:
            history_query = """
                WITH student_scores AS (
                    SELECT 
                        sa.session_id,
                        SUM(COALESCE(sa.ai_score, 0)) as total_score
                    FROM student_answers sa
                    WHERE sa.student_id = ?
                    GROUP BY sa.session_id
                ),
                class_scores AS (
                    SELECT 
                        sa.session_id,
                        sa.student_id,
                        SUM(COALESCE(sa.ai_score, 0)) as total_score
                    FROM student_answers sa
                    WHERE sa.session_id IN (SELECT session_id FROM student_scores)
                    GROUP BY sa.session_id, sa.student_id
                ),
                rankings AS (
                    SELECT 
                        cs1.session_id,
                        COUNT(DISTINCT cs1.student_id) + 1 as rank
                    FROM class_scores cs1
                    JOIN student_scores ss ON cs1.session_id = ss.session_id
                    WHERE cs1.total_score > ss.total_score
                    GROUP BY cs1.session_id
                ),
                class_stats AS (
                    SELECT 
                        cs.session_id,
                        COUNT(DISTINCT cs.student_id) as total_students,
                        AVG(cs.total_score) as avg_score
                    FROM class_scores cs
                    GROUP BY cs.session_id
                )
                SELECT 
                    es.name as exam_name,
                    es.start_time as exam_time,
                    ss.total_score as score,
                    COALESCE(r.rank, 1) as class_rank,
                    cs.total_students,
                    cs.avg_score,
                    es.exam_score as total_possible_score
                FROM student_scores ss
                JOIN exam_sessions es ON ss.session_id = es.id
                LEFT JOIN rankings r ON ss.session_id = r.session_id
                JOIN class_stats cs ON ss.session_id = cs.session_id
                ORDER BY es.start_time DESC
            """
            print(f"执行历史查询: student_id={result['student']['id']}")  # 调试日志
            
            success, history = execute_query(history_query, (result['student']['id'],))
            print(f"历史查询结果: success={success}, history={history}")  # 调试日志
            
            if success and history:
                result['history'] = [{
                    'exam_name': h['exam_name'],
                    'exam_time': h['exam_time'],
                    'score': h['score'],
                    'total_score': h['total_possible_score'],
                    'score_percentage': round(h['score'] / h['total_possible_score'] * 100, 1) if h['total_possible_score'] else 0,
                    'class_rank': f"{h['class_rank']}/{h['total_students']}",
                    'vs_average': round(float(h['score']) - float(h['avg_score']), 1) if h['avg_score'] else 0
                } for h in history]
        
        print("返回数据:", result)  # 调试日志
        return jsonify(result)
        
    except Exception as e:
        print(f"获取学生历史成绩失败: {e}")  # 调试日志
        import traceback
        traceback.print_exc()  # 打印完整的错误堆栈
        return jsonify({'error': str(e)}), 500

# 添加中文字体支持
pdfmetrics.registerFont(TTFont('SimSun', 'simsun.ttc'))

# 添加导出相关的路由
@app.route('/api/analysis/export', methods=['POST'])
@login_required
def export_analysis():
    """导出分析报告"""
    try:
        data = request.get_json()
        print("收到导出请求:", data)  # 调试日志
        
        export_type = data.get('type')
        report_type = data.get('report_type')
        format_type = data.get('format')
        session_id = data.get('session_id')
        student_id = data.get('student_id')
        
        if not all([export_type, report_type, format_type]):
            return jsonify({'error': '缺少必要参数'}), 400
            
        if export_type == 'exam' and not session_id:
            return jsonify({'error': '缺少考试场次ID'}), 400
            
        if export_type == 'student' and not student_id:
            return jsonify({'error': '缺少学生ID'}), 400
            
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{export_type}_{report_type}_{timestamp}"
        
        try:
            # 根据不同的导出类型和格式调用相应的处理函数
            if export_type == 'exam':
                if report_type == 'analysis':
                    file_path = generate_exam_analysis_report(session_id, format_type, filename)
                elif report_type == 'questions':
                    file_path = generate_question_analysis_report(session_id, format_type, filename)
                else:  # scores
                    file_path = generate_score_summary_report(session_id, format_type, filename)
            else:  # student
                if report_type == 'personal':
                    file_path = generate_personal_report(student_id, format_type, filename)
                elif report_type == 'ability':
                    file_path = generate_ability_report(student_id, format_type, filename)
                else:  # improvement
                    file_path = generate_improvement_report(student_id, format_type, filename)
                    
            print(f"文件已生成: {file_path}")  # 调试日志
            
            # 记录导出操作
            user_id = get_current_user_id()
            if user_id:  # 只在获取到用户ID时记录日志
                log_export(user_id, export_type, report_type, format_type, session_id, student_id)
            
            # 返回文件下载链接
            return jsonify({
                'success': True,
                'file_url': url_for('download_report', filename=os.path.basename(file_path))
            })
            
        except Exception as e:
            print(f"生成报告失败: {e}")  # 调试日志
            return jsonify({'error': f'生成报告失败: {str(e)}'}), 500
            
    except Exception as e:
        print(f"导出请求处理失败: {e}")  # 调试日志
        return jsonify({'error': f'导出失败: {str(e)}'}), 500

def log_export(user_id, export_type, report_type, format_type, session_id=None, student_id=None):
    """记录导出操作"""
    query = """
        INSERT INTO export_logs 
        (user_id, export_type, report_type, format_type, session_id, student_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    execute_query(query, (user_id, export_type, report_type, format_type, session_id, student_id))

def get_current_user_id():
    """获取当前用户ID"""
    if 'email' in session:
        query = "SELECT id FROM users WHERE email = ?"
        success, result = execute_query(query, (session['email'],))
        if success and result:
            return result[0]['id']
    return None

@app.route('/api/analysis/download/<filename>')
@login_required
def download_report(filename):
    """下载生成的报告"""
    try:
        return send_from_directory('exports', filename, as_attachment=True)
    except Exception as e:
        return jsonify({'error': '文件下载失败'}), 404

# 报告生成函数
def generate_pdf_exam_analysis(session_info, stats, filename):
    """生成 PDF 格式的考试分析报告"""
    file_path = os.path.join('exports', f'{filename}.pdf')
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    
    # 创建内容
    styles = getSampleStyleSheet()
    story = []
    
    # 添加标题
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName='SimSun',
        fontSize=16,
        spaceAfter=30
    )
    story.append(Paragraph(f"考试分析报告 - {session_info['name']}", title_style))
    
    # 添加考试基本信息
    info_style = ParagraphStyle(
        'CustomInfo',
        parent=styles['Normal'],
        fontName='SimSun',
        fontSize=12,
        spaceAfter=10
    )
    info_text = f"科目: {session_info['subject']}<br/>"
    info_text += f"时间: {session_info['start_time']} 至 {session_info['end_time']}<br/>"
    info_text += f"时长: {calculate_duration(session_info['start_time'], session_info['end_time'])}<br/>"
    story.append(Paragraph(info_text, info_style))
    
    # 添加统计数据
    stats_style = ParagraphStyle(
        'CustomStats',
        parent=styles['Normal'],
        fontName='SimSun',
        fontSize=12,
        spaceAfter=10
    )
    stats_text = f"平均分: {stats['average_score']}<br/>"
    stats_text += f"及格率: {stats['pass_rate']}%<br/>"
    stats_text += f"最高分: {stats['highest_score']}<br/>"
    story.append(Paragraph(stats_text, stats_style))
    
    # 添加分数分布统计表
    data = [['分数段', '人数']]
    for score_range in ['90-100', '80-89', '70-79', '60-69', '0-59']:
        count = stats.get(score_range, 0)
        data.append([score_range, str(count)])
    
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'SimSun'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ])
    table = Table(data)
    table.setStyle(table_style)
    story.append(table)
    
    # 添加分析结论
    conclusion_style = ParagraphStyle(
        'CustomConclusion',
        parent=styles['Normal'],
        fontName='SimSun',
        fontSize=12,
        spaceAfter=10
    )
    conclusion_text = generate_analysis_conclusion(stats['average_score'], stats['pass_rate'])
    story.append(Paragraph(conclusion_text, conclusion_style))
    
    # 生成 PDF
    doc.build(story)
    return file_path

def generate_excel_exam_analysis(session_info, stats, filename):
    """生成 Excel 格式的考试分析报告"""
    file_path = os.path.join('exports', f'{filename}.xlsx')
    wb = Workbook()
    ws = wb.active
    
    # 添加标题
    ws.append(['考试分析报告'])
    ws.merge_cells('A1:D1')
    ws['A1'].font = Font(name='SimSun', size=16, bold=True)
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    
    # 添加考试基本信息
    ws.append(['考试名称', session_info['name']])
    ws.append(['科目', session_info['subject']])
    ws.append(['时间', f"{session_info['start_time']} 至 {session_info['end_time']}"])
    ws.append(['时长', calculate_duration(session_info['start_time'], session_info['end_time'])])
    
    # 添加统计数据
    ws.append(['平均分', stats['average_score']])
    ws.append(['及格率', f"{stats['pass_rate']}%"])
    ws.append(['最高分', stats['highest_score']])
    
    # 添加分数分布统计表
    ws.append(['分数分布统计'])
    ws.append(['分数段', '人数'])
    for score_range in ['90-100', '80-89', '70-79', '60-69', '0-59']:
        count = stats.get(score_range, 0)
        ws.append([score_range, count])
    
    # 添加分析结论
    ws.append(['分析结论'])
    ws.append([generate_analysis_conclusion(stats['average_score'], stats['pass_rate'])])
    
    # 设置单元格格式
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            cell.font = Font(name='SimSun')
            cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # 调整列宽
    for column_letter in ['A', 'B', 'C', 'D']:
        ws.column_dimensions[column_letter].width = 15
    
    # 保存 Excel 文件
    wb.save(file_path)
    return file_path

def generate_word_exam_analysis(session_info, stats, filename):
    """生成 Word 格式的考试分析报告"""
    file_path = os.path.join('exports', f'{filename}.docx')
    doc = Document()
    
    # 添加标题
    doc.add_heading('考试分析报告', level=1)
    
    # 添加考试基本信息
    info_table = doc.add_table(rows=4, cols=2)
    info_table.style = 'Table Grid'
    info_table.cell(0, 0).text = '考试名称'
    info_table.cell(0, 1).text = session_info['name']
    info_table.cell(1, 0).text = '科目'
    info_table.cell(1, 1).text = session_info['subject']
    info_table.cell(2, 0).text = '时间'
    info_table.cell(2, 1).text = f"{session_info['start_time']} 至 {session_info['end_time']}"
    info_table.cell(3, 0).text = '时长'
    info_table.cell(3, 1).text = calculate_duration(session_info['start_time'], session_info['end_time'])
    
    # 添加统计数据
    stats_table = doc.add_table(rows=3, cols=2)
    stats_table.style = 'Table Grid'
    stats_table.cell(0, 0).text = '平均分'
    stats_table.cell(0, 1).text = str(stats['average_score'])
    stats_table.cell(1, 0).text = '及格率'
    stats_table.cell(1, 1).text = f"{stats['pass_rate']}%"
    stats_table.cell(2, 0).text = '最高分'
    stats_table.cell(2, 1).text = str(stats['highest_score'])
    
    # 添加分数分布统计表
    doc.add_heading('分数分布统计', level=2)
    score_dist_table = doc.add_table(rows=6, cols=2)
    score_dist_table.style = 'Table Grid'
    score_dist_table.cell(0, 0).text = '分数段'
    score_dist_table.cell(0, 1).text = '人数'
    for i, score_range in enumerate(['90-100', '80-89', '70-79', '60-69', '0-59'], start=1):
        count = stats.get(score_range, 0)
        score_dist_table.cell(i, 0).text = score_range
        score_dist_table.cell(i, 1).text = str(count)
    
    # 添加分析结论
    doc.add_heading('分析结论', level=2)
    conclusion = doc.add_paragraph()
    conclusion.add_run(generate_analysis_conclusion(stats['average_score'], stats['pass_rate']))
    
    # 保存 Word 文件
    doc.save(file_path)
    return file_path

def generate_analysis_conclusion(average_score, pass_rate):
    """生成分析结论"""
    conclusion = []
    
    # 分析平均分
    if average_score >= 85:
        conclusion.append("本次考试整体成绩优秀，学生掌握程度很好。")
    elif average_score >= 75:
        conclusion.append("本次考试整体成绩良好，大部分学生掌握了主要知识点。")
    elif average_score >= 60:
        conclusion.append("本次考试整体成绩一般，学生的知识掌握还有提升空间。")
    else:
        conclusion.append("本次考试整体成绩不理想，需要加强基础知识的巩固。")
    
    # 分析及格率
    if pass_rate >= 90:
        conclusion.append(f"及格率达到{pass_rate}%，说明绝大多数学生达到了基本要求。")
    elif pass_rate >= 80:
        conclusion.append(f"及格率为{pass_rate}%，大部分学生达到了基本要求。")
    elif pass_rate >= 60:
        conclusion.append(f"及格率为{pass_rate}%，仍有部分学生未能达到基本要求，需要进行针对性辅导。")
    else:
        conclusion.append(f"及格率仅为{pass_rate}%，建议进行全面的知识点复习和强化训练。")
    
    # 添加建议
    if average_score < 60 or pass_rate < 60:
        conclusion.append("建议：\n1. 组织专题复习，针对性讲解重点难点\n2. 增加练习量，强化基础知识\n3. 开展一对一辅导，帮助学习困难学生")
    elif average_score < 75 or pass_rate < 80:
        conclusion.append("建议：\n1. 查漏补缺，巩固薄弱环节\n2. 适当增加练习的深度和难度\n3. 鼓励学生主动提问，及时解决疑难问题")
    else:
        conclusion.append("建议：\n1. 保持良好的学习状态\n2. 进一步提高解题能力和知识应用能力\n3. 可以尝试更具挑战性的题目")
    
    return "\n".join(conclusion)

def generate_exam_analysis_report(session_id, format_type, filename):
    """生成考试整体分析报告"""
    # 获取考试基本信息
    session_query = """
        SELECT 
            id,
            name, 
            subject, 
            start_time, 
            end_time,
            status
        FROM exam_sessions
        WHERE id = ?
    """
    success, session_info = execute_query(session_query, (session_id,))
    if not success or not session_info:
        raise Exception("获取考试信息失败")
    
    # 将 sqlite3.Row 对象转换为字典
    session_info = dict(session_info[0])
    
    # 获取统计数据
    stats_query = """
        WITH student_total_scores AS (
            SELECT 
                student_id,
                SUM(COALESCE(final_score, ai_score)) as total_score
            FROM student_answers
            WHERE session_id = ?
            GROUP BY student_id
        )
        SELECT 
            ROUND(AVG(total_score), 1) as average_score,
            ROUND((COUNT(CASE WHEN total_score >= 60 THEN 1 END) * 100.0 / COUNT(*)), 1) as pass_rate,
            MAX(total_score) as highest_score
        FROM student_total_scores
    """
    success, stats = execute_query(stats_query, (session_id,))
    if not success:
        raise Exception("获取统计数据失败")
    
    # 如果没有统计数据，提供默认值
    stats = dict(stats[0]) if stats else {
        'average_score': 0,
        'pass_rate': 0,
        'highest_score': 0
    }
    
    # 获取分数分布数据
    distribution_query = """
        WITH student_total_scores AS (
            SELECT 
                student_id,
                SUM(COALESCE(final_score, ai_score)) as total_score
            FROM student_answers
            WHERE session_id = ?
            GROUP BY student_id
        )
        SELECT 
            CASE 
                WHEN total_score >= 90 THEN '90-100'
                WHEN total_score >= 80 THEN '80-89'
                WHEN total_score >= 70 THEN '70-79'
                WHEN total_score >= 60 THEN '60-69'
                ELSE '0-59'
            END as score_range,
            COUNT(*) as student_count
        FROM student_total_scores
        GROUP BY 
            CASE 
                WHEN total_score >= 90 THEN '90-100'
                WHEN total_score >= 80 THEN '80-89'
                WHEN total_score >= 70 THEN '70-79'
                WHEN total_score >= 60 THEN '60-69'
                ELSE '0-59'
            END
        ORDER BY score_range DESC
    """
    success, distribution = execute_query(distribution_query, (session_id,))
    
    # 将分布数据转换为字典格式
    distribution_dict = {}
    if success and distribution:
        for row in distribution:
            distribution_dict[row['score_range']] = row['student_count']
    
    # 将分布数据添加到统计数据中
    stats.update(distribution_dict)
    
    # 根据不同格式生成报告
    if format_type == 'pdf':
        return generate_pdf_exam_analysis(session_info, stats, filename)
    elif format_type == 'excel':
        return generate_excel_exam_analysis(session_info, stats, filename)
    else:  # word
        return generate_word_exam_analysis(session_info, stats, filename)

def generate_question_analysis_report(session_id, format_type, filename):
    """生成题目分析报告"""
    # 获取题目分析数据
    query = """
        SELECT 
            q.question_text,
            qa.average_score_rate,
            qa.difficulty_coefficient,
            qa.discrimination_degree
        FROM question_analysis qa
        JOIN questions q ON qa.question_id = q.id
        WHERE qa.session_id = ?
        ORDER BY q.question_order
    """
    success, analysis = execute_query(query, (session_id,))
    if not success or not analysis:
        raise Exception("获取题目分析数据失败")
    
    # 根据不同格式生成报告
    if format_type == 'pdf':
        return generate_pdf_question_analysis(analysis, filename)
    elif format_type == 'excel':
        return generate_excel_question_analysis(analysis, filename)
    else:  # word
        return generate_word_question_analysis(analysis, filename)

def generate_pdf_question_analysis(analysis, filename):
    """生成 PDF 格式的题目分析报告"""
    file_path = os.path.join('exports', f'{filename}.pdf')
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    
    # 创建内容
    styles = getSampleStyleSheet()
    story = []
    
    # 添加标题
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName='SimSun',
        fontSize=16,
        spaceAfter=30
    )
    story.append(Paragraph("题目分析报告", title_style))
    
    # 添加说明文字
    content_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontName='SimSun',
        fontSize=12,
        spaceAfter=12
    )
    
    # 创建表格数据
    table_data = [['题目', '平均得分率', '难度系数', '区分度']]  # 表头
    for item in analysis:
        table_data.append([
            item['question_text'],
            f"{item['average_score_rate']*100:.1f}%",
            f"{item['difficulty_coefficient']:.2f}",
            f"{item['discrimination_degree']:.2f}"
        ])
    
    # 创建表格样式
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'SimSun'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'SimSun'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])
    
    # 创建表格
    table = Table(table_data)
    table.setStyle(table_style)
    
    # 添加表格到内容中
    story.append(table)
    
    # 生成 PDF
    doc.build(story)
    return file_path

def generate_excel_question_analysis(analysis, filename):
    """生成 Excel 格式的题目分析报告"""
    file_path = os.path.join('exports', f'{filename}.xlsx')
    wb = Workbook()
    ws = wb.active
    ws.title = "题目分析"
    
    # 添加标题
    ws['A1'] = "题目分析报告"
    ws.merge_cells('A1:D1')
    
    # 添加说明
    ws['A3'] = "本报告包含各题目的平均得分率、难度系数和区分度分析"
    ws.merge_cells('A3:D3')
    
    # 添加表头
    headers = ['题目', '平均得分率', '难度系数', '区分度']
    for col, header in enumerate(headers, 1):
        ws.cell(row=5, column=col, value=header)
    
    # 添加数据
    for row, item in enumerate(analysis, 6):
        ws.cell(row=row, column=1, value=item['question_text'])
        ws.cell(row=row, column=2, value=f"{item['average_score_rate']*100:.1f}%")
        ws.cell(row=row, column=3, value=f"{item['difficulty_coefficient']:.2f}")
        ws.cell(row=row, column=4, value=f"{item['discrimination_degree']:.2f}")
        
        # 添加难度等级说明
        difficulty = item['difficulty_coefficient']
        if difficulty >= 0.7:
            ws.cell(row=row, column=3).comment = Comment('难度较大', '题目分析')
        elif difficulty <= 0.3:
            ws.cell(row=row, column=3).comment = Comment('难度较小', '题目分析')
        
        # 添加区分度等级说明
        discrimination = item['discrimination_degree']
        if discrimination >= 0.4:
            ws.cell(row=row, column=4).comment = Comment('区分度良好', '题目分析')
        elif discrimination <= 0.2:
            ws.cell(row=row, column=4).comment = Comment('区分度待改进', '题目分析')
    
    # 添加图例说明
    legend_row = len(analysis) + 7
    ws[f'A{legend_row}'] = "说明："
    ws[f'A{legend_row+1}'] = "难度系数：0-0.3为简单题，0.3-0.7为中等难度，0.7-1.0为困难题"
    ws[f'A{legend_row+2}'] = "区分度：0.4以上为良好，0.2-0.4为一般，0.2以下需改进"
    ws.merge_cells(f'A{legend_row+1}:D{legend_row+1}')
    ws.merge_cells(f'A{legend_row+2}:D{legend_row+2}')
    
    # 设置列宽
    ws.column_dimensions['A'].width = 50  # 题目列宽
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15
    
    # 设置标题格式
    title_cell = ws['A1']
    title_cell.font = Font(size=14, bold=True)
    title_cell.alignment = Alignment(horizontal='center')
    
    # 设置说明文字格式
    desc_cell = ws['A3']
    desc_cell.font = Font(italic=True)
    desc_cell.alignment = Alignment(horizontal='center')
    
    # 设置表头格式
    for cell in ws[5]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')
        cell.fill = PatternFill(start_color='E0E0E0', end_color='E0E0E0', fill_type='solid')
    
    # 设置数据单元格格式
    for row in ws.iter_rows(min_row=6, max_row=5+len(analysis)):
        for i, cell in enumerate(row):
            cell.alignment = Alignment(horizontal='center' if i > 0 else 'left')
            
            # 为不同的得分率添加不同的颜色
            if i == 1:  # 平均得分率列
                score = float(cell.value.strip('%'))
                if score >= 80:
                    cell.fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
                elif score <= 40:
                    cell.fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
    
    # 设置图例说明格式
    for row in range(legend_row, legend_row+3):
        cell = ws[f'A{row}']
        cell.font = Font(size=9, italic=True)
        cell.alignment = Alignment(horizontal='left')
    
    # 添加边框
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    for row in ws.iter_rows(min_row=5, max_row=5+len(analysis)):
        for cell in row:
            cell.border = thin_border
    
    # 保存文件
    wb.save(file_path)
    return file_path

def generate_word_question_analysis(analysis, filename):
    """生成 Word 格式的题目分析报告"""
    file_path = os.path.join('exports', f'{filename}.docx')
    doc = Document()
    
    # 添加标题
    doc.add_heading("题目分析报告", 0)
    
    # 添加说明
    doc.add_paragraph("本报告包含各题目的平均得分率、难度系数和区分度分析")
    
    # 创建表格
    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    
    # 设置表头
    header_cells = table.rows[0].cells
    header_cells[0].text = '题目'
    header_cells[1].text = '平均得分率'
    header_cells[2].text = '难度系数'
    header_cells[3].text = '区分度'
    
    # 添加数据
    for item in analysis:
        row_cells = table.add_row().cells
        row_cells[0].text = item['question_text']
        row_cells[1].text = f"{item['average_score_rate']*100:.1f}%"
        row_cells[2].text = f"{item['difficulty_coefficient']:.2f}"
        row_cells[3].text = f"{item['discrimination_degree']:.2f}"
    
    # 调整表格格式
    for row in table.rows:
        for cell in row.cells:
            paragraphs = cell.paragraphs
            for paragraph in paragraphs:
                paragraph.alignment = 1  # 居中对齐
    
    # 保存文件
    doc.save(file_path)
    return file_path

def generate_score_summary_report(session_id, format_type, filename):
    """生成成绩汇总表"""
    # 获取考试基本信息
    session_query = """
        SELECT 
            id,
            name, 
            subject, 
            start_time, 
            end_time,
            status
        FROM exam_sessions
        WHERE id = ?
    """
    success, session_info = execute_query(session_query, (session_id,))
    if not success or not session_info:
        raise Exception("获取考试信息失败")
    
    session_info = dict(session_info[0])
    
    # 获取学生成绩数据
    scores_query = """
        SELECT 
            s.name as student_name,
            s.student_id,
            SUM(COALESCE(final_score, ai_score)) as total_score,
            RANK() OVER (ORDER BY SUM(COALESCE(final_score, ai_score)) DESC) as rank
        FROM student_answers sa
        JOIN students s ON sa.student_id = s.id
        WHERE sa.session_id = ?
        GROUP BY sa.student_id
        ORDER BY total_score DESC
    """
    success, scores = execute_query(scores_query, (session_id,))
    if not success:
        raise Exception("获取成绩数据失败")
    
    scores = [dict(score) for score in scores]
    
    # 根据不同格式生成报告
    if format_type == 'pdf':
        return generate_pdf_score_summary(session_info, scores, filename)
    elif format_type == 'excel':
        return generate_excel_score_summary(session_info, scores, filename)
    else:  # word
        return generate_word_score_summary(session_info, scores, filename)

def generate_pdf_score_summary(session_info, scores, filename):
    """生成 PDF 格式的成绩汇总表"""
    file_path = os.path.join('exports', f'{filename}.pdf')
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    
    # 创建内容
    styles = getSampleStyleSheet()
    story = []
    
    # 添加标题
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName='SimSun',
        fontSize=16,
        spaceAfter=30
    )
    story.append(Paragraph(f"成绩汇总表 - {session_info['name']}", title_style))
    
    # 添加考试信息
    info_style = ParagraphStyle(
        'CustomInfo',
        parent=styles['Normal'],
        fontName='SimSun',
        fontSize=12,
        spaceAfter=10
    )
    info_text = f"科目: {session_info['subject']}<br/>"
    info_text += f"考试时间: {session_info['start_time']} 至 {session_info['end_time']}<br/>"
    story.append(Paragraph(info_text, info_style))
    
    # 创建成绩表格
    data = [['排名', '姓名', '学号', '总分']]
    for score in scores:
        data.append([
            str(score['rank']),
            score['student_name'],
            score['student_id'],
            str(score['total_score'])
        ])
    
    # 设置表格样式
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'SimSun'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ])
    
    table = Table(data)
    table.setStyle(table_style)
    story.append(table)
    
    # 生成 PDF
    doc.build(story)
    return file_path

def generate_excel_score_summary(session_info, scores, filename):
    """生成 Excel 格式的成绩汇总表"""
    file_path = os.path.join('exports', f'{filename}.xlsx')
    wb = Workbook()
    ws = wb.active
    
    # 添加标题
    ws['A1'] = f"成绩汇总表 - {session_info['name']}"
    ws.merge_cells('A1:D1')
    ws['A1'].font = Font(name='SimSun', size=16, bold=True)
    ws['A1'].alignment = Alignment(horizontal='center')
    
    # 添加考试信息
    ws['A2'] = f"科目: {session_info['subject']}"
    ws.merge_cells('A2:D2')
    ws['A3'] = f"考试时间: {session_info['start_time']} 至 {session_info['end_time']}"
    ws.merge_cells('A3:D3')
    
    # 添加表头
    headers = ['排名', '姓名', '学号', '总分']
    for col, header in enumerate(headers, 1):
        ws.cell(row=4, column=col, value=header)
    
    # 添加成绩数据
    for row, score in enumerate(scores, 5):
        ws.cell(row=row, column=1, value=score['rank'])
        ws.cell(row=row, column=2, value=score['student_name'])
        ws.cell(row=row, column=3, value=score['student_id'])
        ws.cell(row=row, column=4, value=score['total_score'])
    
    # 设置样式
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=4):
        for cell in row:
            cell.font = Font(name='SimSun')
            cell.alignment = Alignment(horizontal='center')
    
    # 设置列宽
    ws.column_dimensions['A'].width = 10
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 10
    
    # 保存文件
    wb.save(file_path)
    return file_path

def generate_word_score_summary(session_info, scores, filename):
    """生成 Word 格式的成绩汇总表"""
    file_path = os.path.join('exports', f'{filename}.docx')
    doc = Document()
    
    # 添加标题
    doc.add_heading(f"成绩汇总表 - {session_info['name']}", 0)
    
    # 添加考试信息
    doc.add_paragraph(f"科目: {session_info['subject']}")
    doc.add_paragraph(f"考试时间: {session_info['start_time']} 至 {session_info['end_time']}")
    
    # 创建成绩表格
    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    
    # 添加表头
    header_cells = table.rows[0].cells
    header_cells[0].text = '排名'
    header_cells[1].text = '姓名'
    header_cells[2].text = '学号'
    header_cells[3].text = '总分'
    
    # 添加成绩数据
    for score in scores:
        row_cells = table.add_row().cells
        row_cells[0].text = str(score['rank'])
        row_cells[1].text = score['student_name']
        row_cells[2].text = score['student_id']
        row_cells[3].text = str(score['total_score'])
    
    # 设置表格格式
    for row in table.rows:
        for cell in row.cells:
            cell.paragraphs[0].alignment = 1  # 居中对齐
    
    # 保存文件
    doc.save(file_path)
    return file_path

def generate_personal_report(student_id, format_type, filename):
    """生成个人成绩报告"""
    # 获取学生基本信息
    student_query = """
        SELECT 
            s.id,
            s.name,
            s.student_id,
            s.class_name
        FROM students s
        WHERE s.id = ?
    """
    success, student_info = execute_query(student_query, (student_id,))
    if not success or not student_info:
        raise Exception("获取学生信息失败")
    
    student_info = dict(student_info[0])
    
    # 获取考试历史记录
    history_query = """
        WITH exam_scores AS (
            SELECT 
                es.id as session_id,
                es.name as exam_name,
                es.start_time as exam_time,
                SUM(COALESCE(sa.final_score, sa.ai_score)) as score,
                (SELECT SUM(score) FROM questions WHERE session_id = es.id) as total_score,
                RANK() OVER (
                    PARTITION BY es.id 
                    ORDER BY SUM(COALESCE(sa.final_score, sa.ai_score)) DESC
                ) as class_rank,
                AVG(SUM(COALESCE(sa.final_score, sa.ai_score))) OVER (
                    PARTITION BY es.id
                ) as avg_score
            FROM exam_sessions es
            JOIN student_answers sa ON es.id = sa.session_id
            WHERE sa.student_id = ?
            GROUP BY es.id, es.name, es.start_time
        )
        SELECT 
            exam_name,
            exam_time,
            score,
            total_score,
            ROUND(score * 100.0 / total_score, 1) as score_percentage,
            class_rank,
            ROUND(score - avg_score, 1) as vs_average
        FROM exam_scores
        ORDER BY exam_time DESC
    """
    success, history = execute_query(history_query, (student_id,))
    if not success:
        raise Exception("获取历史记录失败")
    
    history = [dict(h) for h in history]
    
    # 获取答题分析数据
    analysis_query = """
        SELECT 
            q.question_text,
            q.question_type,
            q.score as total_score,
            COALESCE(sa.final_score, sa.ai_score) as score,
            sa.answer_text,
            sa.ai_feedback,
            sa.manual_feedback,
            sa.review_status
        FROM student_answers sa
        JOIN questions q ON sa.question_id = q.id
        WHERE sa.student_id = ?
        ORDER BY sa.session_id DESC, q.question_order
    """
    success, analysis = execute_query(analysis_query, (student_id,))
    if not success:
        raise Exception("获取答题分析失败")
    
    analysis = [dict(a) for a in analysis]
    
    # 根据不同格式生成报告
    if format_type == 'pdf':
        return generate_pdf_personal_report(student_info, history, analysis, filename)
    elif format_type == 'excel':
        return generate_excel_personal_report(student_info, history, analysis, filename)
    else:  # word
        return generate_word_personal_report(student_info, history, analysis, filename)

def generate_pdf_personal_report(student_info, history, analysis, filename):
    """生成 PDF 格式的个人成绩报告"""
    file_path = os.path.join('exports', f'{filename}.pdf')
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    
    # 创建内容
    styles = getSampleStyleSheet()
    story = []
    
    # 添加标题
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName='SimSun',
        fontSize=16,
        spaceAfter=30
    )
    story.append(Paragraph("个人成绩分析报告", title_style))
    
    # 添加学生信息
    info_style = ParagraphStyle(
        'CustomInfo',
        parent=styles['Normal'],
        fontName='SimSun',
        fontSize=12,
        spaceAfter=10
    )
    info_text = f"姓名: {student_info['name']}<br/>"
    info_text += f"学号: {student_info['student_id']}<br/>"
    story.append(Paragraph(info_text, info_style))
    
    # 添加成绩历史表格
    if history:
        data = [['考试名称', '考试时间', '得分', '班级排名', '与平均分差']]
        for h in history:
            data.append([
                h['exam_name'],
                h['exam_time'],
                str(h['score']),
                f"{h['class_rank']}/{h['total_students']}",
                f"{h['score'] - h['avg_score']:.1f}"
            ])
        
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'SimSun'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        
        table = Table(data)
        table.setStyle(table_style)
        story.append(table)
        
        # 添加趋势分析
        trend_style = ParagraphStyle(
            'CustomTrend',
            parent=styles['Normal'],
            fontName='SimSun',
            fontSize=12,
            spaceAfter=10
        )
        
        # 计算成绩趋势
        scores = [h['score'] for h in history]
        avg_scores = [h['avg_score'] for h in history]
        
        trend_text = "成绩趋势分析:<br/>"
        if len(scores) > 1:
            if scores[0] > scores[-1]:
                trend_text += "• 成绩呈上升趋势<br/>"
            elif scores[0] < scores[-1]:
                trend_text += "• 成绩呈下降趋势<br/>"
            else:
                trend_text += "• 成绩保持稳定<br/>"
        
        # 分析与平均分的关系
        vs_avg = [s - a for s, a in zip(scores, avg_scores)]
        if all(v > 0 for v in vs_avg):
            trend_text += "• 持续高于班级平均水平<br/>"
        elif all(v < 0 for v in vs_avg):
            trend_text += "• 需要加强，提高到班级平均水平<br/>"
        else:
            trend_text += "• 成绩波动，建议保持稳定性<br/>"
        
        story.append(Paragraph(trend_text, trend_style))
    else:
        story.append(Paragraph("暂无历史成绩记录", info_style))
    
    # 添加答题分析表格
    if analysis:
        analysis_style = ParagraphStyle(
            'CustomAnalysis',
            parent=styles['Normal'],
            fontName='SimSun',
            fontSize=12,
            spaceAfter=10
        )
        
        # 创建表格数据
        table_data = [['题目', '总分', '得分', '得分率', '点评']]
        for a in analysis:
            table_data.append([
                a['question_text'],
                str(a['total_score']),
                str(a['score']),
                f"{a['score'] / a['total_score'] * 100:.1f}%",
                a['ai_feedback'] or a['manual_feedback'] or '无'
            ])
        
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'SimSun'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        
        table = Table(table_data)
        table.setStyle(table_style)
        story.append(table)
        
        # 添加总体建议
        suggestion_style = ParagraphStyle(
            'CustomSuggestion',
            parent=styles['Normal'],
            fontName='SimSun',
            fontSize=12,
            spaceAfter=10
        )
        
        # 根据得分情况给出建议
        avg_score_rate = sum(a['score'] / a['total_score'] for a in analysis) / len(analysis)
        suggestion_text = "总体建议:<br/>"
        
        if avg_score_rate >= 0.8:
            suggestion_text += """
            • 继续保持良好的学习状态<br/>
            • 可以尝试更具挑战性的题目<br/>
            • 帮助其他同学，提高自己的理解深度<br/>
            """
        elif avg_score_rate >= 0.6:
            suggestion_text += """
            • 查漏补缺，巩固薄弱环节<br/>
            • 增加练习量，提高解题速度<br/>
            • 及时总结错题，避免重复错误<br/>
            """
        else:
            suggestion_text += """
            • 重点复习基础知识点<br/>
            • 制定详细的学习计划<br/>
            • 建议参加课后辅导<br/>
            • 多与老师和同学交流学习方法<br/>
            """
        
        story.append(Paragraph(suggestion_text, suggestion_style))
    else:
        story.append(Paragraph("暂无答题分析数据", info_style))
    
    # 生成 PDF
    doc.build(story)
    return file_path

def generate_excel_personal_report(student_info, history, analysis, filename):
    """生成 Excel 格式的个人成绩报告"""
    file_path = os.path.join('exports', f'{filename}.xlsx')
    wb = Workbook()
    ws = wb.active
    
    # 添加标题
    ws['A1'] = "个人成绩分析报告"
    ws.merge_cells('A1:E1')
    ws['A1'].font = Font(name='SimSun', size=16, bold=True)
    ws['A1'].alignment = Alignment(horizontal='center')
    
    # 添加学生信息
    ws['A2'] = f"姓名: {student_info['name']}"
    ws['A3'] = f"学号: {student_info['student_id']}"
    ws.merge_cells('A2:E2')
    ws.merge_cells('A3:E3')
    
    if history:
        # 添加成绩历史表格
        headers = ['考试名称', '考试时间', '得分', '班级排名', '与平均分差']
        for col, header in enumerate(headers, 1):
            ws.cell(row=4, column=col, value=header)
        
        for row, h in enumerate(history, 5):
            ws.cell(row=row, column=1, value=h['exam_name'])
            ws.cell(row=row, column=2, value=h['exam_time'])
            ws.cell(row=row, column=3, value=h['score'])
            ws.cell(row=row, column=4, value=f"{h['class_rank']}/{h['total_students']}")
            ws.cell(row=row, column=5, value=f"{h['score'] - h['avg_score']:.1f}")
        
        # 添加趋势分析
        trend_row = len(history) + 6
        ws.cell(row=trend_row, column=1, value="成绩趋势分析")
        ws.merge_cells(f'A{trend_row}:E{trend_row}')
        
        scores = [h['score'] for h in history]
        avg_scores = [h['avg_score'] for h in history]
        
        trend_row += 1
        if len(scores) > 1:
            if scores[0] > scores[-1]:
                ws.cell(row=trend_row, column=1, value="• 成绩呈上升趋势")
            elif scores[0] < scores[-1]:
                ws.cell(row=trend_row, column=1, value="• 成绩呈下降趋势")
            else:
                ws.cell(row=trend_row, column=1, value="• 成绩保持稳定")
        
        trend_row += 1
        vs_avg = [s - a for s, a in zip(scores, avg_scores)]
        if all(v > 0 for v in vs_avg):
            ws.cell(row=trend_row, column=1, value="• 持续高于班级平均水平")
        elif all(v < 0 for v in vs_avg):
            ws.cell(row=trend_row, column=1, value="• 需要加强，提高到班级平均水平")
        else:
            ws.cell(row=trend_row, column=1, value="• 成绩波动，建议保持稳定性")
    else:
        ws['A4'] = "暂无历史成绩记录"
        ws.merge_cells('A4:E4')
    
    # 添加答题分析表格
    if analysis:
        # 添加表头
        headers = ['题目', '总分', '得分', '得分率', '点评']
        for col, header in enumerate(headers, 1):
            ws.cell(row=5, column=col, value=header)
        
        # 添加答题分析数据
        for row, item in enumerate(analysis, 6):
            ws.cell(row=row, column=1, value=item['question_text'])
            ws.cell(row=row, column=2, value=item['total_score'])
            ws.cell(row=row, column=3, value=item['score'])
            ws.cell(row=row, column=4, value=f"{item['score'] / item['total_score'] * 100:.1f}%")
            
            # 合并AI点评和教师点评
            feedback = []
            if item['ai_feedback']:
                feedback.append(f"AI点评: {item['ai_feedback']}")
            if item['manual_feedback']:
                feedback.append(f"教师点评: {item['manual_feedback']}")
            ws.cell(row=row, column=5, value="\n".join(feedback))
        
        # 添加总体建议
        suggestion_row = len(analysis) + 7
        ws.cell(row=suggestion_row, column=1, value="总体建议")
        ws.merge_cells(f'A{suggestion_row}:E{suggestion_row}')
        
        # 计算平均得分率
        avg_score_rate = sum(a['score'] / a['total_score'] for a in analysis) / len(analysis)
        
        # 根据得分情况给出建议
        suggestions = []
        if avg_score_rate >= 0.8:
            suggestions.extend([
                "• 继续保持良好的学习状态",
                "• 可以尝试更具挑战性的题目",
                "• 帮助其他同学，提高自己的理解深度"
            ])
        elif avg_score_rate >= 0.6:
            suggestions.extend([
                "• 查漏补缺，巩固薄弱环节",
                "• 增加练习量，提高解题速度",
                "• 及时总结错题，避免重复错误"
            ])
        else:
            suggestions.extend([
                "• 重点复习基础知识点",
                "• 制定详细的学习计划",
                "• 建议参加课后辅导",
                "• 多与老师和同学交流学习方法"
            ])
        
        for i, suggestion in enumerate(suggestions):
            ws.cell(row=suggestion_row+1+i, column=1, value=suggestion)
            ws.merge_cells(f'A{suggestion_row+1+i}:E{suggestion_row+1+i}')
    else:
        ws['A5'] = "暂无答题分析数据"
        ws.merge_cells('A5:E5')
    
    # 设置样式
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=5):
        for cell in row:
            cell.font = Font(name='SimSun')
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    # 设置表头格式
    for cell in ws[5]:
        cell.font = Font(name='SimSun', bold=True)
        cell.fill = PatternFill(start_color='E0E0E0', end_color='E0E0E0', fill_type='solid')
    
    # 添加边框
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    for row in ws.iter_rows(min_row=5, max_row=5+len(analysis)):
        for cell in row:
            cell.border = thin_border
    
    # 保存文件
    wb.save(file_path)
    return file_path

def generate_word_personal_report(student_info, history, analysis, filename):
    """生成 Word 格式的个人成绩报告"""
    file_path = os.path.join('exports', f'{filename}.docx')
    doc = Document()
    
    # 添加标题
    doc.add_heading("个人成绩分析报告", 0)
    
    # 添加学生信息
    doc.add_paragraph(f"姓名: {student_info['name']}")
    doc.add_paragraph(f"学号: {student_info['student_id']}")
    
    if history:
        # 添加成绩历史表格
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        
        # 添加表头
        header_cells = table.rows[0].cells
        header_cells[0].text = '考试名称'
        header_cells[1].text = '考试时间'
        header_cells[2].text = '得分'
        header_cells[3].text = '班级排名'
        header_cells[4].text = '与平均分差'
        
        # 添加数据
        for h in history:
            row_cells = table.add_row().cells
            row_cells[0].text = h['exam_name']
            row_cells[1].text = h['exam_time']
            row_cells[2].text = str(h['score'])
            row_cells[3].text = f"{h['class_rank']}/{h['total_students']}"
            row_cells[4].text = f"{h['score'] - h['avg_score']:.1f}"
        
        # 添加趋势分析
        doc.add_heading("成绩趋势分析", level=1)
        scores = [h['score'] for h in history]
        avg_scores = [h['avg_score'] for h in history]
        
        if len(scores) > 1:
            if scores[0] > scores[-1]:
                doc.add_paragraph("• 成绩呈上升趋势")
            elif scores[0] < scores[-1]:
                doc.add_paragraph("• 成绩呈下降趋势")
            else:
                doc.add_paragraph("• 成绩保持稳定")
        
        vs_avg = [s - a for s, a in zip(scores, avg_scores)]
        if all(v > 0 for v in vs_avg):
            doc.add_paragraph("• 持续高于班级平均水平")
        elif all(v < 0 for v in vs_avg):
            doc.add_paragraph("• 需要加强，提高到班级平均水平")
        else:
            doc.add_paragraph("• 成绩波动，建议保持稳定性")
    else:
        doc.add_paragraph("暂无历史成绩记录")
    
    # 添加答题分析表格
    if analysis:
        # 添加答题分析表格
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        
        # 添加表头
        header_cells = table.rows[0].cells
        header_cells[0].text = '题目'
        header_cells[1].text = '总分'
        header_cells[2].text = '得分'
        header_cells[3].text = '得分率'
        header_cells[4].text = '点评'
        
        # 添加答题数据
        for item in analysis:
            score_rate = item['score'] / item['total_score']
            row_cells = table.add_row().cells
            row_cells[0].text = item['question_text']
            row_cells[1].text = str(item['total_score'])
            row_cells[2].text = str(item['score'])
            row_cells[3].text = f"{score_rate*100:.1f}%"
            
            # 合并AI点评和教师点评
            feedback = []
            if item['ai_feedback']:
                feedback.append(f"AI点评: {item['ai_feedback']}")
            if item['manual_feedback']:
                feedback.append(f"教师点评: {item['manual_feedback']}")
            row_cells[4].text = "\n".join(feedback)
        
        # 设置表格格式
        for row in table.rows:
            for cell in row.cells:
                cell.paragraphs[0].alignment = 1  # 居中对齐
                
        # 添加总体建议
        doc.add_heading("总体建议", level=1)
        
        # 计算平均得分率
        avg_score_rate = sum(a['score'] / a['total_score'] for a in analysis) / len(analysis)
        
        # 根据得分情况给出建议
        if avg_score_rate >= 0.8:
            suggestions = [
                "• 继续保持良好的学习状态",
                "• 可以尝试更具挑战性的题目",
                "• 帮助其他同学，提高自己的理解深度"
            ]
        elif avg_score_rate >= 0.6:
            suggestions = [
                "• 查漏补缺，巩固薄弱环节",
                "• 增加练习量，提高解题速度",
                "• 及时总结错题，避免重复错误"
            ]
        else:
            suggestions = [
                "• 重点复习基础知识点",
                "• 制定详细的学习计划",
                "• 建议参加课后辅导",
                "• 多与老师和同学交流学习方法"
            ]
        
        for suggestion in suggestions:
            doc.add_paragraph(suggestion)
    else:
        doc.add_paragraph("暂无答题分析数据")
    
    # 保存文件
    doc.save(file_path)
    return file_path

def generate_ability_report(student_id, format_type, filename):
    """生成能力诊断报告"""
    # 获取学生信息
    student_query = """
        SELECT name, student_id
        FROM students
        WHERE id = ?
    """
    success, student_info = execute_query(student_query, (student_id,))
    if not success or not student_info:
        raise Exception("获取学生信息失败")
    
    student_info = dict(student_info[0])
    
    # 获取题型分析数据
    analysis_query = """
        SELECT 
            q.question_type,
            AVG(sa.final_score * 1.0 / q.score) as avg_score_rate,
            COUNT(*) as question_count
        FROM student_answers sa
        JOIN questions q ON sa.question_id = q.id
        WHERE sa.student_id = ?
        GROUP BY q.question_type
    """
    success, analysis = execute_query(analysis_query, (student_id,))
    if not success:
        raise Exception("获取题型分析失败")
    
    analysis = [dict(a) for a in (analysis or [])]
    
    # 根据不同格式生成报告
    if format_type == 'pdf':
        return generate_pdf_ability_report(student_info, analysis, filename)
    elif format_type == 'excel':
        return generate_excel_ability_report(student_info, analysis, filename)
    else:  # word
        return generate_word_ability_report(student_info, analysis, filename)

def generate_improvement_report(student_id, format_type, filename):
    """生成进步建议报告"""
    # 获取学生信息
    student_query = """
        SELECT name, student_id
        FROM students
        WHERE id = ?
    """
    success, student_info = execute_query(student_query, (student_id,))
    if not success or not student_info:
        raise Exception("获取学生信息失败")
    
    student_info = dict(student_info[0])
    
    # 获取最近考试的详细分析
    analysis_query = """
        WITH latest_exam AS (
            SELECT session_id
            FROM student_answers
            WHERE student_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        )
        SELECT 
            q.question_text,
            q.score as total_score,
            sa.final_score,
            sa.ai_feedback,
            sa.manual_feedback
        FROM student_answers sa
        JOIN questions q ON sa.question_id = q.id
        JOIN latest_exam le ON sa.session_id = le.session_id
        WHERE sa.student_id = ?
    """
    success, analysis = execute_query(analysis_query, (student_id, student_id))
    if not success:
        raise Exception("获取答题分析失败")
    
    analysis = [dict(a) for a in (analysis or [])]
    
    # 根据不同格式生成报告
    if format_type == 'pdf':
        return generate_pdf_improvement_report(student_info, analysis, filename)
    elif format_type == 'excel':
        return generate_excel_improvement_report(student_info, analysis, filename)
    else:  # word
        return generate_word_improvement_report(student_info, analysis, filename)

def generate_pdf_ability_report(student_info, analysis, filename):
    """生成 PDF 格式的能力诊断报告"""
    file_path = os.path.join('exports', f'{filename}.pdf')
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    
    # 创建内容
    styles = getSampleStyleSheet()
    story = []
    
    # 添加标题和学生信息
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName='SimSun',
        fontSize=16,
        spaceAfter=30
    )
    story.append(Paragraph("能力诊断报告", title_style))
    
    info_style = ParagraphStyle(
        'CustomInfo',
        parent=styles['Normal'],
        fontName='SimSun',
        fontSize=12,
        spaceAfter=10
    )
    info_text = f"姓名: {student_info['name']}<br/>"
    info_text += f"学号: {student_info['student_id']}<br/>"
    story.append(Paragraph(info_text, info_style))
    
    # 添加题型分析表格
    if analysis:
        data = [['题型', '平均得分率', '题目数量']]
        for a in analysis:
            data.append([
                a['question_type'],
                f"{a['avg_score_rate']*100:.1f}%",
                str(a['question_count'])
            ])
        
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'SimSun'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        
        table = Table(data)
        table.setStyle(table_style)
        story.append(table)
        
        # 添加能力分析
        analysis_style = ParagraphStyle(
            'CustomAnalysis',
            parent=styles['Normal'],
            fontName='SimSun',
            fontSize=12,
            spaceAfter=10
        )
        
        # 找出优势和劣势题型
        sorted_analysis = sorted(analysis, key=lambda x: x['avg_score_rate'], reverse=True)
        strengths = [a for a in sorted_analysis if a['avg_score_rate'] >= 0.8]
        weaknesses = [a for a in sorted_analysis if a['avg_score_rate'] < 0.6]
        
        if strengths:
            strength_text = "优势题型:<br/>"
            for s in strengths:
                strength_text += f"• {s['question_type']}: {s['avg_score_rate']*100:.1f}%<br/>"
            story.append(Paragraph(strength_text, analysis_style))
        
        if weaknesses:
            weakness_text = "需要提升的题型:<br/>"
            for w in weaknesses:
                weakness_text += f"• {w['question_type']}: {w['avg_score_rate']*100:.1f}%<br/>"
            story.append(Paragraph(weakness_text, analysis_style))
    else:
        story.append(Paragraph("暂无题型分析数据", info_style))
    
    # 生成 PDF
    doc.build(story)
    return file_path

def generate_pdf_improvement_report(student_info, analysis, filename):
    """生成 PDF 格式的进步建议报告"""
    file_path = os.path.join('exports', f'{filename}.pdf')
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    
    # 创建内容
    styles = getSampleStyleSheet()
    story = []
    
    # 添加标题和学生信息
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName='SimSun',
        fontSize=16,
        spaceAfter=30
    )
    story.append(Paragraph("学习进步建议", title_style))
    
    info_style = ParagraphStyle(
        'CustomInfo',
        parent=styles['Normal'],
        fontName='SimSun',
        fontSize=12,
        spaceAfter=10
    )
    info_text = f"姓名: {student_info['name']}<br/>"
    info_text += f"学号: {student_info['student_id']}<br/>"
    story.append(Paragraph(info_text, info_style))
    
    if analysis:
        # 添加答题分析
        for i, a in enumerate(analysis, 1):
            question_style = ParagraphStyle(
                'CustomQuestion',
                parent=styles['Normal'],
                fontName='SimSun',
                fontSize=12,
                spaceAfter=10
            )
            
            score_rate = a['final_score'] / a['total_score']
            question_text = f"题目 {i}:<br/>"
            question_text += f"得分率: {score_rate*100:.1f}%<br/>"
            if a['ai_feedback']:
                question_text += f"AI点评: {a['ai_feedback']}<br/>"
            if a['manual_feedback']:
                question_text += f"教师点评: {a['manual_feedback']}<br/>"
            
            story.append(Paragraph(question_text, question_style))
        
        # 添加总体建议
        suggestion_style = ParagraphStyle(
            'CustomSuggestion',
            parent=styles['Normal'],
            fontName='SimSun',
            fontSize=12,
            spaceAfter=10
        )
        
        # 根据得分情况给出建议
        avg_score_rate = sum(a['final_score'] / a['total_score'] for a in analysis) / len(analysis)
        suggestion_text = "总体建议:<br/>"
        
        if avg_score_rate >= 0.8:
            suggestion_text += """
            • 继续保持良好的学习状态<br/>
            • 可以尝试更具挑战性的题目<br/>
            • 帮助其他同学，提高自己的理解深度<br/>
            """
        elif avg_score_rate >= 0.6:
            suggestion_text += """
            • 查漏补缺，巩固薄弱环节<br/>
            • 增加练习量，提高解题速度<br/>
            • 及时总结错题，避免重复错误<br/>
            """
        else:
            suggestion_text += """
            • 重点复习基础知识点<br/>
            • 制定详细的学习计划<br/>
            • 建议参加课后辅导<br/>
            • 多与老师和同学交流学习方法<br/>
            """
        
        story.append(Paragraph(suggestion_text, suggestion_style))
    else:
        story.append(Paragraph("暂无答题分析数据", info_style))
    
    # 生成 PDF
    doc.build(story)
    return file_path

def generate_excel_improvement_report(student_info, analysis, filename):
    """生成 Excel 格式的进步建议报告"""
    file_path = os.path.join('exports', f'{filename}.xlsx')
    wb = Workbook()
    ws = wb.active
    ws.title = "进步建议报告"
    
    # 添加标题
    ws['A1'] = "学习进步建议报告"
    ws.merge_cells('A1:D1')
    ws['A1'].font = Font(name='SimSun', size=16, bold=True)
    ws['A1'].alignment = Alignment(horizontal='center')
    
    # 添加学生信息
    ws['A2'] = f"姓名: {student_info['name']}"
    ws['A3'] = f"学号: {student_info['student_id']}"
    ws.merge_cells('A2:D2')
    ws.merge_cells('A3:D3')
    
    if analysis:
        # 添加表头
        headers = ['题目', '总分', '得分', '得分率', '点评']
        for col, header in enumerate(headers, 1):
            ws.cell(row=5, column=col, value=header)
        
        # 添加答题分析数据
        for row, item in enumerate(analysis, 6):
            score_rate = item['final_score'] / item['total_score']
            ws.cell(row=row, column=1, value=item['question_text'])
            ws.cell(row=row, column=2, value=item['total_score'])
            ws.cell(row=row, column=3, value=item['final_score'])
            ws.cell(row=row, column=4, value=f"{score_rate*100:.1f}%")
            
            # 合并AI点评和教师点评
            feedback = []
            if item['ai_feedback']:
                feedback.append(f"AI点评: {item['ai_feedback']}")
            if item['manual_feedback']:
                feedback.append(f"教师点评: {item['manual_feedback']}")
            ws.cell(row=row, column=5, value="\n".join(feedback))
        
        # 添加总体建议
        suggestion_row = len(analysis) + 7
        ws.cell(row=suggestion_row, column=1, value="总体建议")
        ws.merge_cells(f'A{suggestion_row}:D{suggestion_row}')
        
        # 计算平均得分率
        avg_score_rate = sum(a['final_score'] / a['total_score'] for a in analysis) / len(analysis)
        
        # 根据得分情况给出建议
        suggestions = []
        if avg_score_rate >= 0.8:
            suggestions.extend([
                "• 继续保持良好的学习状态",
                "• 可以尝试更具挑战性的题目",
                "• 帮助其他同学，提高自己的理解深度"
            ])
        elif avg_score_rate >= 0.6:
            suggestions.extend([
                "• 查漏补缺，巩固薄弱环节",
                "• 增加练习量，提高解题速度",
                "• 及时总结错题，避免重复错误"
            ])
        else:
            suggestions.extend([
                "• 重点复习基础知识点",
                "• 制定详细的学习计划",
                "• 建议参加课后辅导",
                "• 多与老师和同学交流学习方法"
            ])
        
        for i, suggestion in enumerate(suggestions):
            ws.cell(row=suggestion_row+1+i, column=1, value=suggestion)
            ws.merge_cells(f'A{suggestion_row+1+i}:D{suggestion_row+1+i}')
    else:
        ws['A5'] = "暂无答题分析数据"
        ws.merge_cells('A5:D5')
    
    # 设置列宽
    ws.column_dimensions['A'].width = 40  # 题目列宽
    ws.column_dimensions['B'].width = 10
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 10
    ws.column_dimensions['E'].width = 50  # 点评列宽
    
    # 设置样式
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=5):
        for cell in row:
            cell.font = Font(name='SimSun')
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    # 设置表头格式
    for cell in ws[5]:
        cell.font = Font(name='SimSun', bold=True)
        cell.fill = PatternFill(start_color='E0E0E0', end_color='E0E0E0', fill_type='solid')
    
    # 添加边框
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    for row in ws.iter_rows(min_row=5, max_row=5+len(analysis)):
        for cell in row:
            cell.border = thin_border
    
    # 保存文件
    wb.save(file_path)
    return file_path

def generate_word_improvement_report(student_info, analysis, filename):
    """生成 Word 格式的进步建议报告"""
    file_path = os.path.join('exports', f'{filename}.docx')
    doc = Document()
    
    # 添加标题
    doc.add_heading("学习进步建议报告", 0)
    
    # 添加学生信息
    doc.add_paragraph(f"姓名: {student_info['name']}")
    doc.add_paragraph(f"学号: {student_info['student_id']}")
    
    if analysis:
        # 添加答题分析表格
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        
        # 添加表头
        header_cells = table.rows[0].cells
        header_cells[0].text = '题目'
        header_cells[1].text = '总分'
        header_cells[2].text = '得分'
        header_cells[3].text = '得分率'
        header_cells[4].text = '点评'
        
        # 添加答题数据
        for item in analysis:
            score_rate = item['final_score'] / item['total_score']
            row_cells = table.add_row().cells
            row_cells[0].text = item['question_text']
            row_cells[1].text = str(item['total_score'])
            row_cells[2].text = str(item['final_score'])
            row_cells[3].text = f"{score_rate*100:.1f}%"
            
            # 合并AI点评和教师点评
            feedback = []
            if item['ai_feedback']:
                feedback.append(f"AI点评: {item['ai_feedback']}")
            if item['manual_feedback']:
                feedback.append(f"教师点评: {item['manual_feedback']}")
            row_cells[4].text = "\n".join(feedback)
        
        # 设置表格格式
        for row in table.rows:
            for cell in row.cells:
                cell.paragraphs[0].alignment = 1  # 居中对齐
                
        # 添加总体建议
        doc.add_heading("总体建议", level=1)
        
        # 计算平均得分率
        avg_score_rate = sum(a['final_score'] / a['total_score'] for a in analysis) / len(analysis)
        
        # 根据得分情况给出建议
        if avg_score_rate >= 0.8:
            suggestions = [
                "• 继续保持良好的学习状态",
                "• 可以尝试更具挑战性的题目",
                "• 帮助其他同学，提高自己的理解深度"
            ]
        elif avg_score_rate >= 0.6:
            suggestions = [
                "• 查漏补缺，巩固薄弱环节",
                "• 增加练习量，提高解题速度",
                "• 及时总结错题，避免重复错误"
            ]
        else:
            suggestions = [
                "• 重点复习基础知识点",
                "• 制定详细的学习计划",
                "• 建议参加课后辅导",
                "• 多与老师和同学交流学习方法"
            ]
        
        for suggestion in suggestions:
            doc.add_paragraph(suggestion)
    else:
        doc.add_paragraph("暂无答题分析数据")
    
    # 保存文件
    doc.save(file_path)
    return file_path

@app.route('/api/user/info')
@login_required
def get_user_info():
    """获取当前用户信息"""
    if 'email' not in session:
        return jsonify({'error': '未登录'}), 401
        
    query = """
        SELECT id, email, created_at
        FROM users
        WHERE email = ?
    """
    success, result = execute_query(query, (session['email'],))
    
    if not success or not result:
        return jsonify({'error': '获取用户信息失败'}), 500
        
    user = result[0]
    return jsonify({
        'id': user['id'],
        'email': user['email'],
        'created_at': user['created_at']
    })

@app.route('/api/user/change-password', methods=['POST'])
@login_required
def change_password():
    """修改用户密码"""
    if 'email' not in session:
        return jsonify({'error': '未登录'}), 401
        
    data = request.get_json()
    current_password = data.get('currentPassword')
    new_password = data.get('newPassword')
    
    if not all([current_password, new_password]):
        return jsonify({'error': '缺少必要参数'}), 400
        
    # 验证当前密码
    query = "SELECT id, password FROM users WHERE email = ?"
    success, result = execute_query(query, (session['email'],))
    
    if not success or not result:
        return jsonify({'error': '用户不存在'}), 404
        
    user = result[0]
    if current_password != user['password']:  # 实际应用中应使用密码哈希比较
        return jsonify({'error': '当前密码错误'}), 400
        
    # 更新密码
    update_query = "UPDATE users SET password = ? WHERE id = ?"
    success, _ = execute_query(update_query, (new_password, user['id']))
    
    if not success:
        return jsonify({'error': '密码更新失败'}), 500
        
    # 记录密码修改操作
    log_query = """
        INSERT INTO operation_logs (user_id, operation_type, operation_details) 
        VALUES (?, ?, ?)
    """
    execute_query(log_query, (user['id'], 'change_password', f'Password changed from {request.remote_addr}'))
    
    return jsonify({'message': '密码修改成功'})

@app.route('/extracted_files/<path:filename>')
def uploaded_file(filename):
    """提供上传文件的访问"""
    try:
        return send_from_directory(EXTRACT_FOLDER, filename)
    except Exception as e:
        logger.error(f'访问文件失败: {filename} - {str(e)}')
        return jsonify({'error': '文件不存在'}), 404

@app.route('/api/start-grading', methods=['POST'])
@login_required
def start_grading():
    """开始自动阅卷"""
    try:
        # 获取考试场次ID
        session_id = request.form.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'message': '缺少考试场次ID'}), 400

        # 处理上传的文件
        files = []
        for key in request.files:
            file = request.files[key]
            if file and allowed_file(file.filename):
                # 保存文件到 extracted_files 目录
                filename = secure_filename(file.filename)
                save_path = os.path.join(EXTRACT_FOLDER, filename)
                file.save(save_path)
                files.append(save_path)

        if not files:
            return jsonify({'success': False, 'message': '未上传有效的试卷文件'}), 400

        # 获取考试信息
        query = """
            SELECT id, name, subject, exam_score
            FROM exam_sessions
            WHERE id = ?
        """
        success, exam_info = execute_query(query, (session_id,))
        if not success or not exam_info:
            return jsonify({'success': False, 'message': '获取考试信息失败'}), 500
        
        exam_info = exam_info[0]
        total_score = float(exam_info['exam_score'])

        # 处理每个上传的文件
        for file_path in files:
            try:
                # 1. 使用 slip 模块进行 OCR 识别
                from split_and_ocr.slip import split_columns_and_rows
                # 为每个文件创建单独的输出文件
                ocr_output = f"ocr_results_{os.path.basename(file_path)}.txt"
                split_columns_and_rows(file_path, ocr_output)

                # 2. 分割题目和答案
                from split_and_ocr.read.questionsplit import readexit
                readexit()

                # 3. 获取学生信息（从文件名或OCR结果中提取）
                # 这里假设文件名格式为：学号_姓名.pdf
                student_info = os.path.basename(file_path).split('.')[0].split('_')
                if len(student_info) != 2:
                    raise Exception("文件名格式错误，应为：学号_姓名.pdf")
                
                student_id, student_name = student_info

                # 检查学生是否存在，不存在则创建
                check_query = "SELECT id FROM students WHERE student_id = ?"
                success, student = execute_query(check_query, (student_id,))
                
                if not success:
                    raise Exception("查询学生信息失败")
                
                if not student:
                    # 创建新学生
                    insert_query = """
                        INSERT INTO students (name, student_id)
                        VALUES (?, ?)
                    """
                    success, student = execute_query(insert_query, (student_name, student_id))
                    if not success:
                        raise Exception("创建学生记录失败")
                    student_db_id = student.lastrowid
                else:
                    student_db_id = student[0]['id']

                # 4. AI 评分
                # 读取分割后的答案文件
                current_dir = os.path.dirname(os.path.abspath(__file__))
                read_dir = os.path.join(current_dir, "split_and_ocr", "read")
                
                # 获取read目录下所有txt文件
                os.chdir(read_dir)  # 切换到read目录
                files = [f for f in os.listdir() if f.endswith('.txt')]
                
                # 定义题型和对应的文件名匹配模式
                question_patterns = {
                    '选择题': r'选择.+',
                    '填空题': r'填空.+',
                    '简答题': r'简答.+',
                    '判断题': r'判断.+',
                    '编程题': r'编程.+'
                }
                
                # 处理每种题型
                for q_type, pattern in question_patterns.items():
                    # 匹配对应题型的文件
                    matched_files = [f for f in files if re.search(pattern, f)]
                    
                    if matched_files:  # 如果找到匹配的文件
                        answer_file = os.path.join(read_dir, matched_files[0])
                        with open(answer_file, 'r', encoding='utf-8') as f:
                            answers = f.read()
                        f.close()
                            
                        # 从数据库获取该类型的题目信息
                        if q_type == '选择题':
                            query = """
                                SELECT q.id, q.question_text, q.question_score,
                                       mcq.options, mcq.correct_option, mcq.explanation
                                FROM questions q
                                JOIN multiple_choice_questions mcq ON q.id = mcq.question_id
                                WHERE q.session_id = ? AND q.question_type = '选择题'
                                ORDER BY q.question_order
                            """
                        elif q_type == '编程题':
                            query = """
                                SELECT q.id, q.question_text, q.question_score,
                                       pq.test_cases, pq.expected_output, pq.solution_template,
                                       pq.hints
                                FROM questions q
                                JOIN programming_questions pq ON q.id = pq.question_id
                                WHERE q.session_id = ? AND q.question_type = '编程题'
                                ORDER BY q.question_order
                            """
                        elif q_type == '简答题':
                            query = """
                                SELECT q.id, q.question_text, q.question_score,
                                       saq.model_answer, saq.key_points, saq.grading_criteria
                                FROM questions q
                                JOIN short_answer_questions saq ON q.id = saq.question_id
                                WHERE q.session_id = ? AND q.question_type = '简答题'
                                ORDER BY q.question_order
                            """
                        elif q_type == '判断题':
                            query = """
                                SELECT q.id, q.question_text, q.question_score,
                                       tfq.correct_answer, tfq.explanation
                                FROM questions q
                                JOIN true_false_questions tfq ON q.id = tfq.question_id
                                WHERE q.session_id = ? AND q.question_type = '判断题'
                                ORDER BY q.question_order
                            """
                        else:  # 填空题
                            query = """
                                SELECT q.id, q.question_text, q.question_score,
                                       fbq.correct_answer, fbq.alternative_answers,
                                       fbq.explanation
                                FROM questions q
                                JOIN fill_blank_questions fbq ON q.id = fbq.question_id
                                WHERE q.session_id = ? AND q.question_type = '填空题'
                                ORDER BY q.question_order
                            """
                        
                        success, questions = execute_query(query, (session_id,))
                        
                        if not success:
                            raise Exception(f"获取{q_type}题目信息失败")

                        # 构建评分提示
                        if q_type == '选择题':
                            prompt = f"""
                            请对以下选择题答案进行评分。

                            考试信息：
                            - 考试名称：{exam_info['name']}
                            - 科目：{exam_info['subject']}
                            
                            题目信息：
                            {[f'''
                            第{idx+1}题（{q['question_score']}分）
                            题目：{q['question_text']}
                            选项：{q['options']}
                            正确答案：{q['correct_option']}
                            解析：{q['explanation'] or '无'}
                            ''' for idx, q in enumerate(questions)]}
                            
                            学生答案：
                            {answers}

                            请根据以下规则评分：
                            1. 答案完全正确得满分
                            2. 答案错误得0分
                            3. 如果有多个选择题，请分别给出每道题的得分
                            4. 给出评价时，说明答错的原因和正确的解析

                            请以JSON格式返回结果，包含以下字段：
                            score: 总分数（数字）
                            feedback: 详细的评价意见（文字）
                            question_scores: 每道题的得分列表（数组）
                            """
                        elif q_type == '填空题':
                            prompt = f"""
                            请对以下填空题答案进行评分。

                            考试信息：
                            - 考试名称：{exam_info['name']}
                            - 科目：{exam_info['subject']}
                            
                            题目信息：
                            {[f'''
                            第{idx+1}题（{q['question_score']}分）
                            题目：{q['question_text']}
                            标准答案：{q['correct_answer']}
                            其他可接受答案：{q['alternative_answers'] or '无'}
                            解析：{q['explanation'] or '无'}
                            ''' for idx, q in enumerate(questions)]}
                            
                            学生答案：
                            {answers}

                            请根据以下规则评分：
                            1. 答案完全匹配标准答案或可接受答案之一得满分
                            2. 答案部分正确酌情给分（根据关键词匹配程度）
                            3. 答案完全错误得0分
                            4. 如果有多个空，请分别给出每个空的得分
                            5. 给出评价时，指出错误之处，并给出正确答案

                            请以JSON格式返回结果，包含以下字段：
                            score: 总分数（数字）
                            feedback: 详细的评价意见（文字）
                            question_scores: 每道题的得分列表（数组）
                            """
                        else:  # 简答题
                            prompt = f"""
                            请对以下简答题答案进行评分。

                            考试信息：
                            - 考试名称：{exam_info['name']}
                            - 科目：{exam_info['subject']}
                            
                            题目信息：
                            {[f'''
                            第{idx+1}题（{q['question_score']}分）
                            题目：{q['question_text']}
                            参考答案：{q['model_answer']}
                            关键点：{q['key_points']}
                            评分标准：{q['grading_criteria'] or '无'}
                            ''' for idx, q in enumerate(questions)]}
                            
                            学生答案：
                            {answers}

                            请根据以下规则评分：
                            1. 答案要点完全正确且表述清晰得满分
                            2. 根据答案要点的覆盖程度和表述准确性酌情给分：
                               - 核心概念准确：40%（关键点覆盖程度）
                               - 论述完整性：30%（答案结构和逻辑）
                               - 例子/证据支持：20%（实例说明）
                               - 语言表达：10%（表述清晰度）
                            3. 给出评价时：
                               - 指出答案中正确的关键点
                               - 指出缺失或错误的关键点
                               - 给出改进建议
                               - 提供完整的参考答案

                            请以JSON格式返回结果，包含以下字段：
                            score: 总分数（数字）
                            feedback: 详细的评价意见（文字）
                            question_scores: 每道题的得分列表（数组）
                            scoring_details: {
                                "核心概念": 分数,
                                "论述完整性": 分数,
                                "例子支持": 分数,
                                "语言表达": 分数
                            }
                            """
                            
                        # 使用AI评分
                        from split_and_ocr.ai import aiapi
                        result = aiapi("", prompt)
                        try:
                            score_info = json.loads(result)
                        except:
                            score_info = {
                                'score': 0,
                                'feedback': '评分失败',
                                'question_scores': [0] * len(questions)
                            }

                        # 保存每道题的评分结果
                        for idx, question in enumerate(questions):
                            question_score = score_info.get('question_scores', [])[idx] if idx < len(score_info.get('question_scores', [])) else 0
                            
                            insert_query = """
                                INSERT INTO student_answers 
                                (session_id, student_id, question_id, question_type, 
                                 answer_text, ai_score, ai_feedback, scoring_details)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """
                            success, _ = execute_query(
                                insert_query, 
                                (session_id, student_db_id, question['id'], q_type,
                                 answers, question_score, score_info['feedback'],
                                 json.dumps(score_info.get('scoring_details', {})))
                            )
                            if not success:
                                raise Exception(f"{q_type}第{idx+1}题评分结果保存失败")

            except Exception as e:
                print(f"处理文件 {file_path} 时出错: {str(e)}")
                continue
            finally:
                # 清理临时文件
                if os.path.exists(file_path):
                    os.remove(file_path)

        # 更新考试场次状态
        update_query = """
            UPDATE exam_sessions 
            SET status = 'graded' 
            WHERE id = ?
        """
        success, _ = execute_query(update_query, (session_id,))
        
        if not success:
            return jsonify({'success': False, 'message': '更新考试状态失败'}), 500

        return jsonify({
            'success': True,
            'message': '阅卷完成'
        })

    except Exception as e:
        print(f"阅卷过程出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'阅卷过程出错: {str(e)}'
        }), 500

# 在应用启动时初始化数据库表
if __name__ == '__main__':
    # 确保数据库目录存在
    os.makedirs('database', exist_ok=True)
    # 启动应用
    app.run(debug=True)

