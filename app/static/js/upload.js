document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const fileList = document.getElementById('fileList');
    const fileItems = document.getElementById('fileItems');
    const uploadActions = document.getElementById('uploadActions');
    const uploadForm = document.getElementById('uploadForm');
    const spinner = document.getElementById('spinner');

    // Drag and drop
    dropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', function() {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const dt = new DataTransfer();
        for (const file of e.dataTransfer.files) {
            const ext = file.name.split('.').pop().toLowerCase();
            if (['csv', 'xlsx', 'xls'].includes(ext)) {
                dt.items.add(file);
            }
        }
        fileInput.files = dt.files;
        updateFileList(dt.files);
    });

    fileInput.addEventListener('change', function() {
        updateFileList(this.files);
    });

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function updateFileList(files) {
        if (files.length === 0) {
            fileList.style.display = 'none';
            uploadActions.style.display = 'none';
            return;
        }

        fileItems.innerHTML = '';
        for (const file of files) {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.innerHTML = '<span class="file-name">' + file.name + '</span>' +
                           '<span class="file-size">' + formatFileSize(file.size) + '</span>';
            fileItems.appendChild(item);
        }

        fileList.style.display = 'block';
        uploadActions.style.display = 'block';
    }

    uploadForm.addEventListener('submit', function() {
        spinner.style.display = 'flex';
    });
});
