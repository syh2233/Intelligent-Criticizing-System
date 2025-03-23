window.tailwind.config = {
  darkMode: ['class'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))'
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))'
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))'
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))'
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))'
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))'
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))'
        },
      },
    }
  }
};

document.addEventListener('DOMContentLoaded', function() {
  // 添加安全检查函数
  function safeGetElement(id) {
    return document.getElementById(id);
  }
  
  // 安全地添加事件监听器
  function safeAddEventListener(element, event, callback) {
    if (element) {
      element.addEventListener(event, callback);
    }
  }

  const saveSessionButton = safeGetElement('save-session-button');
  const sessionList = safeGetElement('session-list');
  
  if (saveSessionButton && sessionList) {
    const sessionListUl = sessionList.querySelector('ul');
    if (sessionListUl) {
      saveSessionButton.addEventListener('click', () => {
        const newSessionName = safeGetElement('new-session-name');
        if (newSessionName && newSessionName.value.trim()) {
          const newListItem = document.createElement('li');
          newListItem.textContent = newSessionName.value.trim();
          sessionListUl.appendChild(newListItem);
          newSessionName.value = '';
        }
      });
    }
  }

  // 获取上传相关元素
  const imageUpload = safeGetElement('image-upload');
  const fileUpload = safeGetElement('file-upload');
  const previewContainer = safeGetElement('preview-container');
  const imagePreview = safeGetElement('image-preview');
  const filePreview = safeGetElement('file-preview');
  const imagePreviewGrid = safeGetElement('image-preview-grid');
  const filePreviewContent = safeGetElement('file-preview-content');
  const clearImages = safeGetElement('clear-images');
  const clearFile = safeGetElement('clear-file');

  // 处理图片上传
  safeAddEventListener(imageUpload, 'change', function(e) {
    if (!previewContainer || !imagePreview || !imagePreviewGrid) return;
    
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      previewContainer.classList.remove('hidden');
      imagePreview.classList.remove('hidden');
      imagePreviewGrid.innerHTML = '';

      files.forEach(file => {
        const reader = new FileReader();
        reader.onload = function(e) {
          // 创建预览元素
          const previewItem = document.createElement('div');
          previewItem.className = 'relative group';
          previewItem.innerHTML = `
            <img src="${e.target.result}" 
                 class="w-full h-40 object-cover rounded-md" 
                 alt="${file.name}"/>
            <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity duration-200 rounded-md flex items-center justify-center">
              <span class="text-white text-sm">${file.name}</span>
            </div>
          `;
          imagePreviewGrid.appendChild(previewItem);

          // 上传图片到服务器
          uploadImage(e.target.result);
        };
        reader.readAsDataURL(file);
      });
    }
  });

  // 处理文件上传
  safeAddEventListener(fileUpload, 'change', function(e) {
    if (!previewContainer || !filePreview || !filePreviewContent) return;
    
    const file = e.target.files[0];
    if (file) {
      previewContainer.classList.remove('hidden');
      filePreview.classList.remove('hidden');
      
      // 显示文件预览
      const fileIcon = getFileIcon(file.name);
      const fileSize = formatFileSize(file.size);
      
      filePreviewContent.innerHTML = `
        <div class="bg-muted p-4 rounded-md">
          <div class="flex items-center space-x-3">
            <span class="text-2xl">${fileIcon}</span>
            <div class="flex-grow">
              <p class="font-medium">${file.name}</p>
              <p class="text-sm text-muted-foreground">${fileSize}</p>
            </div>
            <div class="text-sm text-muted-foreground">
              ${getFileType(file.name)}
            </div>
          </div>
        </div>
      `;

      // 上传文件到服务器
      uploadWordFile(file);
    }
  });

  // 清除图片
  safeAddEventListener(clearImages, 'click', function() {
    if (!imageUpload || !imagePreview || !imagePreviewGrid || !previewContainer || !filePreview) return;
    
    imageUpload.value = '';
    imagePreview.classList.add('hidden');
    imagePreviewGrid.innerHTML = '';
    if (filePreview.classList.contains('hidden')) {
      previewContainer.classList.add('hidden');
    }
  });

  // 清除文件
  safeAddEventListener(clearFile, 'click', function() {
    if (!fileUpload || !filePreview || !filePreviewContent || !previewContainer || !imagePreview) return;
    
    fileUpload.value = '';
    filePreview.classList.add('hidden');
    filePreviewContent.innerHTML = '';
    if (imagePreview.classList.contains('hidden')) {
      previewContainer.classList.add('hidden');
    }
  });

  // 上传图片到服务器的函数
  function uploadImage(imageData) {
    fetch('/upload', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ image: imageData })
    })
    .then(response => response.json())
    .then(data => {
      if (data.status === 'success') {
        console.log('图片上传成功:', data.filename);
      } else {
        console.error('图片上传失败:', data.message);
      }
    })
    .catch(error => {
      console.error('上传错误:', error);
    });
  }

  // 上传Word文件到服务器的函数
  function uploadWordFile(file) {
    const formData = new FormData();
    formData.append('word_file', file);

    fetch('/upload-word', {
      method: 'POST',
      body: formData
    })
    .then(response => response.json())
    .then(data => {
      if (data.status === 'success') {
        console.log('Word文件上传成功:', data.filename);
      } else {
        console.error('Word文件上传失败:', data.message);
      }
    })
    .catch(error => {
      console.error('上传错误:', error);
    });
  }

  // 辅助函数
  function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
      'doc': '📄',
      'docx': '📄',
      'zip': '📦',
      'rar': '📦'
    };
    return icons[ext] || '📄';
  }

  function getFileType(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const types = {
      'doc': 'Word文档',
      'docx': 'Word文档',
      'zip': '压缩包',
      'rar': '压缩包'
    };
    return types[ext] || '未知类型';
  }

  function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
});

// 避免重复添加事件监听器，使用安全的方式检查元素
const uploadBtn = document.getElementById('image-upload');
if (uploadBtn) {
  // 检查是否已有事件监听器
  const hasClickListener = uploadBtn._hasClickListener;
  if (!hasClickListener) {
    uploadBtn.addEventListener('click', () => {
      const fileInput = document.getElementById('image-upload');
      if (fileInput) fileInput.click();
    });
    uploadBtn._hasClickListener = true;
  }
  
  // 检查是否已有change事件监听器
  const hasChangeListener = uploadBtn._hasChangeListener;
  if (!hasChangeListener) {
    uploadBtn.addEventListener('change', (event) => {
      const file = event.target.files[0];
      if (file) {
        const previewImage = document.getElementById('preview-container');
        if (!previewImage) return;
        
        const reader = new FileReader();
        reader.onload = (e) => {
          previewImage.src = e.target.result;
          previewImage.style.display = 'block';
          // 发送图片数据到后端
          uploadImage(e.target.result);
        };
        reader.readAsDataURL(file);
      }
    });
    uploadBtn._hasChangeListener = true;
  }
}

function uploadImage(imageData) {
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/upload', true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  
  xhr.onload = function() {
    if (xhr.status === 200) {
      const response = JSON.parse(xhr.responseText);
      if (response.status === 'success') {
        console.log('图片上传成功:', response.filename);
      } else {
        console.error('图片上传失败:', response.message);
      }
    }
  };
  
  xhr.onerror = function() {
    console.error('上传错误');
  };
  
  xhr.send(JSON.stringify({ image: imageData }));
}

// 重写uploadWordFile避免重复定义
function uploadWordFileXHR(file) {
  const formData = new FormData();
  formData.append('word_file', file);
  
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/upload-word', true);
  
  xhr.onload = function() {
    if (xhr.status === 200) {
      const response = JSON.parse(xhr.responseText);
      if (response.status === 'success') {
        console.log('Word文件上传成功:', response.filename);
      } else {
        console.error('Word文件上传失败:', response.message);
      }
    }
  };
  
  xhr.onerror = function() {
    console.error('上传错误');
  };
  
  xhr.send(formData);
}