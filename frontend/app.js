/**
 * AI 智能简历分析系统 - 前端交互逻辑
 *
 * 纯原生 JavaScript，无需构建工具，可直接部署到 GitHub Pages。
 */

// ─── 配置 ───

// 后端 API 地址（部署时修改为实际地址）
// 部署时改为 Render / 阿里云 FC 实际地址
// const API_BASE = 'http://localhost:8000';  // 本地开发
const API_BASE = 'https://ai-resume-analyzer-mujt.onrender.com';  // 线上部署

// ─── 全局状态 ───

const state = {
    resumeId: null,
    fileName: null,
    result: null,
};

// ─── DOM 元素 ───

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ─── 初始化 ───

document.addEventListener('DOMContentLoaded', () => {
    initUpload();
    initAnalyze();
    initReset();
});

// ─── Step 1: 上传 ───

function initUpload() {
    const uploadArea = $('#upload-area');
    const fileInput = $('#file-input');
    const uploadBtn = $('#upload-btn');

    // 点击选择文件
    uploadBtn.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('click', (e) => {
        if (e.target !== uploadBtn) fileInput.click();
    });

    // 拖拽上传
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-over');
    });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    });

    // 文件选择
    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (file) handleFile(file);
    });
}

async function handleFile(file) {
    // 验证文件类型
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        alert('仅支持 PDF 格式的文件');
        return;
    }

    // 验证文件大小 (10MB)
    if (file.size > 10 * 1024 * 1024) {
        alert('文件大小不能超过 10MB');
        return;
    }

    // 显示上传状态
    const uploadArea = $('#upload-area');
    const uploadStatus = $('#upload-status');
    const statusText = $('#status-text');

    uploadArea.style.display = 'none';
    uploadStatus.style.display = 'block';
    statusText.textContent = `正在解析 ${file.name}...`;

    // 上传文件
    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE}/api/upload`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '上传失败');
        }

        const data = await response.json();

        // 保存状态
        state.resumeId = data.resume_id;
        state.fileName = data.filename;

        // 显示文本预览
        statusText.textContent = `✅ 解析完成: ${data.filename}`;
        uploadStatus.querySelector('.status-icon').textContent = '✅';

        if (data.text_preview) {
            const textPreview = $('#text-preview');
            const previewContent = $('#preview-content');
            previewContent.textContent = data.text_preview;
            textPreview.style.display = 'block';
        }

        // 显示 Step 2
        const jdSection = $('#jd-section');
        jdSection.style.display = 'block';
        jdSection.scrollIntoView({ behavior: 'smooth' });

        // 启用分析按钮的条件
        checkAnalyzeReady();
    } catch (error) {
        statusText.textContent = `❌ 上传失败: ${error.message}`;
        uploadStatus.querySelector('.status-icon').textContent = '❌';
        console.error('Upload error:', error);
    }
}

// ─── Step 2: 分析 ───

function initAnalyze() {
    const jdInput = $('#jd-input');
    const analyzeBtn = $('#analyze-btn');

    jdInput.addEventListener('input', checkAnalyzeReady);
    analyzeBtn.addEventListener('click', performAnalysis);
}

function checkAnalyzeReady() {
    const jdInput = $('#jd-input');
    const analyzeBtn = $('#analyze-btn');
    analyzeBtn.disabled = !state.resumeId || !jdInput.value.trim();
}

async function performAnalysis() {
    const jdText = $('#jd-input').value.trim();
    if (!jdText || !state.resumeId) return;

    // 显示结果区域
    const resultSection = $('#result-section');
    resultSection.style.display = 'block';
    resultSection.scrollIntoView({ behavior: 'smooth' });

    // 显示 loading
    $('#loading').style.display = 'block';
    $('#error-box').style.display = 'none';
    $('#method-badges').style.display = 'none';
    $('#score-overview').style.display = 'none';
    $('#info-grid').style.display = 'none';
    $('#match-keywords').style.display = 'none';
    $('#ai-analysis').style.display = 'none';
    $('#actions').style.display = 'none';

    try {
        const response = await fetch(`${API_BASE}/api/analyze/${state.resumeId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_description: jdText }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '分析失败');
        }

        const data = await response.json();
        state.result = data;

        // 渲染结果
        renderResults(data);
    } catch (error) {
        $('#loading').style.display = 'none';
        $('#error-box').style.display = 'block';
        $('#error-message').textContent = `分析失败: ${error.message}`;
        console.error('Analysis error:', error);
    }
}

// ─── Step 3: 结果渲染 ───

function renderResults(data) {
    $('#loading').style.display = 'none';

    // 显示提取和匹配方式标识
    const badges = $('#method-badges');
    badges.style.display = 'flex';

    const extractBadge = $('#badge-extraction');
    extractBadge.textContent = data.extraction_method === 'ai'
        ? '🤖 信息提取: AI 模型'
        : '📋 信息提取: 规则匹配';
    extractBadge.className = 'badge ' + (data.extraction_method === 'ai' ? 'ai' : 'rule');

    const matchBadge = $('#badge-match');
    matchBadge.textContent = data.match_method === 'ai'
        ? '🎯 匹配评分: AI 模型'
        : '📊 匹配评分: 规则匹配';
    matchBadge.className = 'badge ' + (data.match_method === 'ai' ? 'ai' : 'rule');

    const cacheBadge = $('#badge-cache');
    if (data.cached) {
        cacheBadge.style.display = 'inline-flex';
    } else {
        cacheBadge.style.display = 'none';
    }

    const { resume_info, match_result } = data;

    // 评分概览
    if (match_result && match_result.match_detail) {
        renderScoreOverview(match_result.match_detail);
    }

    // 简历信息
    if (resume_info) {
        renderResumeInfo(resume_info);
    }

    // 匹配关键词
    if (match_result) {
        renderMatchKeywords(match_result);
    }

    // AI 分析
    if (match_result && match_result.ai_analysis) {
        $('#ai-analysis').style.display = 'block';
        $('#ai-analysis-text').textContent = match_result.ai_analysis;
    }

    // 操作按钮
    $('#actions').style.display = 'block';

    // 滚动到结果
    $('#result-section').scrollIntoView({ behavior: 'smooth' });
}

function renderScoreOverview(detail) {
    $('#score-overview').style.display = 'flex';

    // 综合评分
    $('#overall-score').textContent = detail.overall_score || 0;

    // 技能匹配
    const skillPct = Math.round((detail.skill_match_rate || 0) * 100);
    $('#skill-rate').textContent = skillPct + '%';
    $('#skill-rate-bar').style.width = skillPct + '%';

    // 经验相关
    const expPct = Math.round((detail.experience_relevance || 0) * 100);
    $('#exp-rate').textContent = expPct + '%';
    $('#exp-rate-bar').style.width = expPct + '%';

    // 学历匹配
    const eduPct = Math.round((detail.education_match || 0) * 100);
    $('#edu-rate').textContent = eduPct + '%';
    $('#edu-rate-bar').style.width = eduPct + '%';
}

function renderResumeInfo(info) {
    $('#info-grid').style.display = 'grid';

    // 基本信息
    const bi = info.basic_info || {};
    $('#info-name').textContent = bi.name || '-';
    $('#info-phone').textContent = bi.phone || '-';
    $('#info-email').textContent = bi.email || '-';
    $('#info-address').textContent = bi.address || '-';

    // 求职意向
    const ji = info.job_intent || {};
    $('#info-position').textContent = ji.position || '-';
    $('#info-salary').textContent = ji.salary || '-';

    // 背景信息
    const bg = info.background_info || {};
    $('#info-years').textContent = bg.work_years || '-';

    // 教育
    const edu = bg.education || {};
    $('#info-degree').textContent = edu.degree || '-';
    $('#info-school').textContent = edu.school || '-';
    $('#info-major').textContent = edu.major || '-';

    // 技能标签
    const skillsContainer = $('#info-skills');
    skillsContainer.innerHTML = '';
    if (bg.skills && bg.skills.length > 0) {
        bg.skills.forEach(skill => {
            const tag = document.createElement('span');
            tag.className = 'skill-tag';
            tag.textContent = skill;
            skillsContainer.appendChild(tag);
        });
    } else {
        skillsContainer.innerHTML = '<span class="no-keywords">未识别到技能</span>';
    }

    // 项目经历
    const projects = bg.project_experiences || [];
    const projectsCard = $('#projects-card');
    const projectsContainer = $('#info-projects');
    if (projects.length > 0) {
        projectsCard.style.display = 'block';
        projectsContainer.innerHTML = '';
        projects.forEach(proj => {
            const div = document.createElement('div');
            div.className = 'project-item';
            div.innerHTML = `
                <h4>${escapeHtml(proj.name || '未命名项目')}</h4>
                <p>${escapeHtml((proj.description || '').substring(0, 200))}</p>
                ${proj.role ? `<span class="role">👤 ${escapeHtml(proj.role)}</span>` : ''}
            `;
            projectsContainer.appendChild(div);
        });
    } else {
        projectsCard.style.display = 'none';
    }
}

function renderMatchKeywords(match) {
    $('#match-keywords').style.display = 'grid';

    // 匹配关键词
    const matchedContainer = $('#matched-tags');
    matchedContainer.innerHTML = '';
    if (match.matched_keywords && match.matched_keywords.length > 0) {
        match.matched_keywords.forEach(kw => {
            const tag = document.createElement('span');
            tag.className = 'keyword-tag matched';
            tag.textContent = kw;
            matchedContainer.appendChild(tag);
        });
    } else {
        matchedContainer.innerHTML = '<span class="no-keywords">暂无</span>';
    }

    // 缺失关键词
    const missingContainer = $('#missing-tags');
    missingContainer.innerHTML = '';
    if (match.missing_keywords && match.missing_keywords.length > 0) {
        match.missing_keywords.forEach(kw => {
            const tag = document.createElement('span');
            tag.className = 'keyword-tag missing';
            tag.textContent = kw;
            missingContainer.appendChild(tag);
        });
    } else {
        missingContainer.innerHTML = '<span class="no-keywords">暂无</span>';
    }
}

// ─── 重置 ───

function initReset() {
    $('#reset-btn').addEventListener('click', reAnalyze);
    $('#new-upload-btn').addEventListener('click', resetAll);
}

// 重新分析：保留已上传的简历，回到 JD 输入步骤
function reAnalyze() {
    state.result = null;

    $('#result-section').style.display = 'none';
    $('#jd-section').style.display = 'block';
    $('#jd-input').value = '';
    $('#analyze-btn').disabled = true;

    $('#jd-section').scrollIntoView({ behavior: 'smooth' });
}

// 完全重置：重新上传新简历
function resetAll() {
    state.resumeId = null;
    state.fileName = null;
    state.result = null;

    $('#upload-area').style.display = 'block';
    $('#upload-status').style.display = 'none';
    $('#text-preview').style.display = 'none';
    $('#jd-section').style.display = 'none';
    $('#jd-input').value = '';
    $('#result-section').style.display = 'none';
    $('#analyze-btn').disabled = true;
    $('#method-badges').style.display = 'none';

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ─── 工具函数 ───

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
