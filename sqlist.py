import sqlite3

# 启用外键约束
conn = sqlite3.connect('database/It_g.db')
cursor = conn.cursor()
cursor.execute('PRAGMA foreign_keys = ON')

# 删除现有表（如果存在）- 注意删除顺序（先删除有外键依赖的表）
cursor.execute('DROP TABLE IF EXISTS score_distribution')
cursor.execute('DROP TABLE IF EXISTS score_statistics')
cursor.execute('DROP TABLE IF EXISTS export_logs')
cursor.execute('DROP TABLE IF EXISTS operation_logs')
cursor.execute('DROP TABLE IF EXISTS student_answers')
cursor.execute('DROP TABLE IF EXISTS question_analysis')
cursor.execute('DROP TABLE IF EXISTS questions')
cursor.execute('DROP TABLE IF EXISTS analysis_reports')
cursor.execute('DROP TABLE IF EXISTS grading_results')
cursor.execute('DROP TABLE IF EXISTS uploaded_papers')
cursor.execute('DROP TABLE IF EXISTS exam_sessions')
cursor.execute('DROP TABLE IF EXISTS students')
cursor.execute('DROP TABLE IF EXISTS users')
cursor.execute('DROP TABLE IF EXISTS multiple_choice_questions')
cursor.execute('DROP TABLE IF EXISTS fill_blank_questions')
cursor.execute('DROP TABLE IF EXISTS short_answer_questions')
cursor.execute('DROP TABLE IF EXISTS true_false_questions')
cursor.execute('DROP TABLE IF EXISTS programming_questions')

# 创建用户表（核心表）
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# 创建学生表（核心表）
cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        student_id TEXT UNIQUE NOT NULL,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
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
        status TEXT NOT NULL CHECK(status IN ('pending', 'ongoing', 'completed', 'graded')),
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
    )
''')

# 创建题库表 - 选择题
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
        explanation TEXT,
        score INTEGER NOT NULL DEFAULT 5,
        difficulty INTEGER NOT NULL DEFAULT 3 CHECK(difficulty BETWEEN 1 AND 5),
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_template BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
    )
''')

# 创建题库表 - 填空题
cursor.execute('''
    CREATE TABLE IF NOT EXISTS fill_blank_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        question_text TEXT NOT NULL,
        correct_answer TEXT NOT NULL,
        alternative_answers TEXT,
        explanation TEXT,
        score INTEGER NOT NULL DEFAULT 5,
        difficulty INTEGER NOT NULL DEFAULT 3 CHECK(difficulty BETWEEN 1 AND 5),
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_template BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
    )
''')

# 创建题库表 - 简答题
cursor.execute('''
    CREATE TABLE IF NOT EXISTS short_answer_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        question_text TEXT NOT NULL,
        reference_answer TEXT NOT NULL,
        key_points TEXT NOT NULL,
        grading_criteria TEXT,
        score INTEGER NOT NULL DEFAULT 10,
        difficulty INTEGER NOT NULL DEFAULT 3 CHECK(difficulty BETWEEN 1 AND 5),
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_template BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
    )
''')

# 创建题库表 - 判断题
cursor.execute('''
    CREATE TABLE IF NOT EXISTS true_false_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        question_text TEXT NOT NULL,
        correct_answer BOOLEAN NOT NULL,
        explanation TEXT,
        score INTEGER NOT NULL DEFAULT 3,
        difficulty INTEGER NOT NULL DEFAULT 3 CHECK(difficulty BETWEEN 1 AND 5),
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_template BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
    )
''')

# 创建题库表 - 编程题
cursor.execute('''
    CREATE TABLE IF NOT EXISTS programming_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        question_text TEXT NOT NULL,
        sample_input TEXT,
        sample_output TEXT,
        test_cases TEXT NOT NULL,
        reference_solution TEXT,
        time_limit INTEGER DEFAULT 1000,
        memory_limit INTEGER DEFAULT 256,
        hints TEXT,
        score INTEGER NOT NULL DEFAULT 20,
        difficulty INTEGER NOT NULL DEFAULT 3 CHECK(difficulty BETWEEN 1 AND 5),
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_template BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
    )
''')

# 创建试卷上传记录表
cursor.execute('''
    CREATE TABLE IF NOT EXISTS uploaded_papers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        file_type TEXT CHECK(file_type IN ('image', 'document')) NOT NULL,
        upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processing_status TEXT CHECK(processing_status IN ('pending', 'processing', 'completed', 'failed')) NOT NULL DEFAULT 'pending',
        ocr_result TEXT,
        FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    )
''')

# 创建题目表（考试中的具体题目）
cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        question_type TEXT NOT NULL CHECK(question_type IN ('multiple_choice', 'fill_blank', 'short_answer', 'true_false', 'programming')),
        question_text TEXT NOT NULL,
        score INTEGER NOT NULL,
        question_order INTEGER NOT NULL,
        source_question_id INTEGER,
        source_table TEXT CHECK(source_table IN ('multiple_choice_questions', 'fill_blank_questions', 'short_answer_questions', 'true_false_questions', 'programming_questions')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE
    )
''')

# 创建学生答案表
cursor.execute('''
    CREATE TABLE IF NOT EXISTS student_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        question_type TEXT NOT NULL CHECK(question_type IN ('multiple_choice', 'fill_blank', 'short_answer', 'true_false', 'programming')),
        answer_text TEXT,
        ai_score REAL CHECK(ai_score >= 0),
        ai_feedback TEXT,
        scoring_details TEXT,
        review_status TEXT DEFAULT 'pending' CHECK(review_status IN ('pending', 'reviewed', 'disputed')),
        reviewed_by INTEGER,
        reviewed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
        FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
    )
''')

# 创建题目分析表
cursor.execute('''
    CREATE TABLE IF NOT EXISTS question_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        average_score_rate REAL NOT NULL CHECK(average_score_rate BETWEEN 0 AND 1),
        difficulty_coefficient REAL NOT NULL CHECK(difficulty_coefficient BETWEEN 0 AND 1),
        discrimination_degree REAL NOT NULL CHECK(discrimination_degree BETWEEN -1 AND 1),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
    )
''')

# 创建成绩统计表
cursor.execute('''
    CREATE TABLE IF NOT EXISTS score_statistics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        average_score FLOAT NOT NULL CHECK(average_score >= 0),
        pass_rate FLOAT NOT NULL CHECK(pass_rate BETWEEN 0 AND 1),
        highest_score FLOAT NOT NULL CHECK(highest_score >= 0),
        highest_score_student_id INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE,
        FOREIGN KEY (highest_score_student_id) REFERENCES students(id) ON DELETE SET NULL
    )
''')

# 创建分数分布表
cursor.execute('''
    CREATE TABLE IF NOT EXISTS score_distribution (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        score_range TEXT NOT NULL,
        student_count INTEGER NOT NULL CHECK(student_count >= 0),
        FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE
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
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE SET NULL,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
    )
''')

# -- 添加 final_score 列到 student_answers 表
# ALTER TABLE student_answers ADD COLUMN final_score REAL CHECK(final_score >= 0);


# 提交更改并关闭连接
conn.commit()
conn.close()
