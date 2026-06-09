document.addEventListener('DOMContentLoaded', function() {
    console.log('OAuth2.0 Server Simulator loaded');
    
    document.querySelectorAll('.code-block').forEach(function(block) {
        block.addEventListener('click', function() {
            const text = this.textContent;
            navigator.clipboard.writeText(text).then(function() {
                showToast('已复制到剪贴板');
            }).catch(function() {
                console.log('Copy failed');
            });
        });
    });
    
    document.querySelectorAll('code.code-inline').forEach(function(code) {
        code.style.cursor = 'pointer';
        code.title = '点击复制';
        code.addEventListener('click', function() {
            const text = this.textContent;
            navigator.clipboard.writeText(text).then(function() {
                showToast('已复制到剪贴板');
            });
        });
    });
});

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        padding: 12px 20px;
        background: ${type === 'success' ? '#38a169' : '#e53e3e'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        animation: slideIn 0.3s ease;
    `;
    document.body.appendChild(toast);
    
    setTimeout(function() {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(function() {
            document.body.removeChild(toast);
        }, 300);
    }, 2500);
}

const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(400px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(400px); opacity: 0; }
    }
`;
document.head.appendChild(style);

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN');
}

function formatDuration(seconds) {
    if (seconds < 60) return `${seconds}秒`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}小时`;
    return `${Math.floor(seconds / 86400)}天`;
}
