/**
 * Reddit Posts Viewer
 * Interactive UI for viewing Reddit posts sorted by score
 * Features: Auto-extract nouns from filename, show all posts with optional filtering
 * Supports viewing comments with nested replies
 */

// State
let allPosts = [];
let filteredPosts = [];
let currentQuery = '';
let matchedSubreddits = [];
let queryNouns = [];
let autoFilterNouns = [];
let showFilteredOnly = false; // Toggle between all posts and filtered

// Common English stop words to filter out
const STOP_WORDS = new Set([
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
    'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
    'shall', 'can', 'need', 'dare', 'ought', 'used', 'it', 'its', 'this', 'that',
    'these', 'those', 'i', 'you', 'he', 'she', 'we', 'they', 'what', 'which', 'who',
    'whom', 'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few',
    'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
    'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now', 'here', 'there',
    'then', 'once', 'if', 'about', 'into', 'through', 'during', 'before', 'after',
    'above', 'below', 'between', 'under', 'again', 'further', 'any', 'how', 'me',
    'my', 'your', 'his', 'her', 'our', 'their', 'am', 'being', 'get', 'got', 'getting',
    'make', 'made', 'making', 'take', 'took', 'taking', 'come', 'came', 'coming',
    'go', 'went', 'going', 'see', 'saw', 'seeing', 'know', 'knew', 'knowing',
    'think', 'thought', 'thinking', 'want', 'wanted', 'wanting', 'give', 'gave',
    'use', 'using', 'find', 'found', 'finding', 'tell', 'told', 'telling', 'ask',
    'asked', 'asking', 'work', 'working', 'seem', 'seemed', 'seeming', 'feel',
    'felt', 'feeling', 'try', 'tried', 'trying', 'leave', 'left', 'leaving', 'put',
    'putting', 'keep', 'kept', 'keeping', 'let', 'letting', 'begin', 'began',
    'beginning', 'show', 'showed', 'showing', 'hear', 'heard', 'hearing', 'play',
    'playing', 'run', 'ran', 'running', 'move', 'moved', 'moving', 'live', 'lived',
    'living', 'believe', 'believed', 'believing', 'bring', 'brought', 'bringing',
    'happen', 'happened', 'happening', 'write', 'wrote', 'writing', 'provide',
    'provided', 'providing', 'sit', 'sat', 'sitting', 'stand', 'stood', 'standing',
    'lose', 'lost', 'losing', 'pay', 'paid', 'paying', 'meet', 'met', 'meeting',
    'include', 'included', 'including', 'continue', 'continued', 'continuing',
    'set', 'setting', 'learn', 'learned', 'learning', 'change', 'changed', 'changing',
    'lead', 'led', 'leading', 'understand', 'understood', 'understanding', 'watch',
    'watched', 'watching', 'follow', 'followed', 'following', 'stop', 'stopped',
    'stopping', 'create', 'created', 'creating', 'speak', 'spoke', 'speaking',
    'read', 'reading', 'spend', 'spent', 'spending', 'grow', 'grew', 'growing',
    'open', 'opened', 'opening', 'walk', 'walked', 'walking', 'win', 'won', 'winning',
    'offer', 'offered', 'offering', 'remember', 'remembered', 'remembering',
    'love', 'loved', 'loving', 'consider', 'considered', 'considering', 'appear',
    'appeared', 'appearing', 'buy', 'bought', 'buying', 'wait', 'waited', 'waiting',
    'serve', 'served', 'serving', 'die', 'died', 'dying', 'send', 'sent', 'sending',
    'expect', 'expected', 'expecting', 'build', 'built', 'building', 'stay', 'stayed',
    'staying', 'fall', 'fell', 'falling', 'cut', 'cutting', 'reach', 'reached',
    'reaching', 'kill', 'killed', 'killing', 'remain', 'remained', 'remaining',
    'suggest', 'suggested', 'suggesting', 'raise', 'raised', 'raising', 'pass',
    'passed', 'passing', 'sell', 'sold', 'selling', 'require', 'required', 'requiring',
    'report', 'reported', 'reporting', 'decide', 'decided', 'deciding', 'pull',
    'pulled', 'pulling', 'reddit', 'json', 'file', 'data', 'posts', 'search',
    'query', 'results', 'scraped', 'scrape'
]);

// Common verbs to exclude (additional)
const COMMON_VERBS = new Set([
    'looking', 'searching', 'find', 'finding', 'found', 'search', 'searched',
    'want', 'wanted', 'needing', 'need', 'needed', 'help', 'helped', 'helping',
    'please', 'thanks', 'thank', 'thankyou', 'hi', 'hello', 'hey', 'ok', 'okay',
    'yes', 'no', 'yeah', 'yep', 'nope', 'pls', 'plz', 'thx', 'ty', 'lol', 'lmao',
    'wtf', 'omg', 'btw', 'imo', 'imho', 'aka', 'etc', 'eg', 'ie'
]);

// DOM Elements
const jsonFileInput = document.getElementById('jsonFile');
const queryInput = document.getElementById('queryInput');
const filterBtn = document.getElementById('filterBtn');
const clearFilterBtn = document.getElementById('clearFilterBtn');
const showAllBtn = document.getElementById('showAllBtn');
const showFilteredBtn = document.getElementById('showFilteredBtn');
const postsContainer = document.getElementById('postsContainer');
const statsContainer = document.getElementById('stats');
const filterInfo = document.getElementById('filterInfo');
const postModal = document.getElementById('postModal');
const modalBody = document.getElementById('modalBody');
const modalClose = document.getElementById('modalClose');

// Initialize
function init() {
    setupEventListeners();
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    jsonFileInput.addEventListener('change', handleFileUpload);
    filterBtn.addEventListener('click', handleFilter);
    clearFilterBtn.addEventListener('click', handleClearFilter);
    showAllBtn.addEventListener('click', () => setViewMode(false));
    showFilteredBtn.addEventListener('click', () => setViewMode(true));
    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleFilter();
    });
    modalClose.addEventListener('click', closeModal);
    postModal.addEventListener('click', (e) => {
        if (e.target === postModal) closeModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && postModal.classList.contains('active')) {
            closeModal();
        }
    });
}

/**
 * Set view mode (all posts or filtered only)
 */
function setViewMode(filtered) {
    showFilteredOnly = filtered;
    
    // Update button states
    showAllBtn.classList.toggle('active', !filtered);
    showFilteredBtn.classList.toggle('active', filtered);
    
    // Re-render posts
    renderPosts();
    updateStats('file', allPosts.length, filteredPosts.length);
}

/**
 * Extract ALL words from filename (not just nouns)
 */
function extractAllWordsFromFilename(filename) {
    let name = filename.replace(/\.json$/i, '');
    name = name.replace(/^reddit_/i, '');
    name = name.replace(/_/g, ' ');
    return extractAllWords(name);
}

/**
 * Extract nouns from filename
 */
function extractNounsFromFilename(filename) {
    let name = filename.replace(/\.json$/i, '');
    name = name.replace(/^reddit_/i, '');
    name = name.replace(/_/g, ' ');
    return extractNouns(name);
}

/**
 * Handle JSON file upload
 */
function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    postsContainer.innerHTML = `
        <div class="empty-state">
            <p>⏳ Loading posts...</p>
        </div>
    `;

    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const data = JSON.parse(e.target.result);
            
            if (data.posts && Array.isArray(data.posts)) {
                loadPosts(data.posts, file.name);
            } else if (Array.isArray(data)) {
                loadPosts(data, file.name);
            } else {
                showError('Invalid JSON format. Expected an array of posts or object with "posts" property.');
            }
        } catch (err) {
            showError('Failed to parse JSON file: ' + err.message);
        }
    };
    reader.readAsText(file);
}

/**
 * Load and display posts
 */
function loadPosts(posts, filename = 'Unknown') {
    if (!posts || posts.length === 0) {
        showError('No posts found in the file.');
        return;
    }

    allPosts = [...posts].sort((a, b) => (b.score || 0) - (a.score || 0));
    
    // Extract ALL words from filename for auto-filtering (not just nouns)
    autoFilterNouns = extractAllWordsFromFilename(filename);
    
    // Auto-populate the query input with the extracted words
    if (autoFilterNouns.length > 0) {
        queryInput.value = autoFilterNouns.join(' ');
    }
    
    // Calculate filtered posts
    if (autoFilterNouns.length > 0) {
        queryNouns = [...autoFilterNouns];
        currentQuery = autoFilterNouns.join(' ');
        
        const allSubreddits = [...new Set(allPosts.map(p => p.subreddit))];
        matchedSubreddits = allSubreddits.filter(subreddit => {
            const subNouns = extractNouns(subreddit);
            return queryNouns.some(qn => 
                subNouns.some(sn => sn.includes(qn) || qn.includes(sn))
            );
        });
        
        const postsWithScores = allPosts.map(post => ({
            post,
            relevance: calculateRelevanceScore(post, queryNouns)
        }));
        
        filteredPosts = postsWithScores
            .filter(item => item.relevance > 0)
            .sort((a, b) => {
                if (b.relevance !== a.relevance) return b.relevance - a.relevance;
                return (b.post.score || 0) - (a.post.score || 0);
            })
            .map(item => item.post);
        
        updateFilterInfo(currentQuery, queryNouns, filteredPosts.length, matchedSubreddits, filename);
    } else {
        filteredPosts = [...allPosts];
        matchedSubreddits = [];
        currentQuery = '';
        queryNouns = [];
        filterInfo.classList.remove('active');
    }

    // Default to showing all posts
    showFilteredOnly = false;
    showAllBtn.classList.add('active');
    showFilteredBtn.classList.remove('active');

    updateStats(filename, allPosts.length, filteredPosts.length);
    renderPosts();
}

/**
 * Update statistics display
 */
function updateStats(source, totalCount, filteredCount) {
    const totalScore = allPosts.reduce((sum, p) => sum + (p.score || 0), 0);
    const avgScore = Math.round(totalScore / allPosts.length);
    const maxScore = Math.max(...allPosts.map(p => p.score || 0));

    const displayCount = showFilteredOnly ? filteredCount : totalCount;
    const label = showFilteredOnly ? 'Filtered Posts' : 'Total Posts';

    statsContainer.innerHTML = `
        <div class="stat-item">
            <div class="stat-value">${displayCount}</div>
            <div class="stat-label">${label}</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">${formatNumber(maxScore)}</div>
            <div class="stat-label">Top Score</div>
        </div>
        <div class="stat-item">
            <div class="stat-value">${formatNumber(avgScore)}</div>
            <div class="stat-label">Avg Score</div>
        </div>
    `;
}

/**
 * Extract nouns from text
 */
function extractNouns(text) {
    if (!text) return [];
    
    const words = text.toLowerCase()
        .replace(/[^a-z0-9\s]/g, ' ')
        .split(/\s+/)
        .filter(word => {
            if (word.length < 2) return false;
            if (STOP_WORDS.has(word)) return false;
            if (COMMON_VERBS.has(word)) return false;
            if (/^\d+$/.test(word) && word.length > 4) return false;
            return true;
        });
    
    return [...new Set(words)];
}

/**
 * Extract ALL words from text (only filter stop words, keep everything else)
 */
function extractAllWords(text) {
    if (!text) return [];
    
    const words = text.toLowerCase()
        .replace(/[^a-z0-9\s]/g, ' ')
        .split(/\s+/)
        .filter(word => {
            if (word.length < 2) return false;
            if (STOP_WORDS.has(word)) return false;
            // Don't filter common verbs - keep all meaningful words
            return true;
        });
    
    return [...new Set(words)];
}

/**
 * Calculate relevance score for a post
 */
function calculateRelevanceScore(post, queryNouns) {
    if (queryNouns.length === 0) return 1;
    
    let score = 0;
    const titleNouns = extractNouns(post.title);
    const subredditNouns = extractNouns(post.subreddit);
    const selftextNouns = extractNouns(post.selftext);
    
    queryNouns.forEach(noun => {
        if (titleNouns.includes(noun)) score += 3;
    });
    
    queryNouns.forEach(noun => {
        if (subredditNouns.some(sn => sn.includes(noun) || noun.includes(sn))) score += 2;
    });
    
    queryNouns.forEach(noun => {
        if (selftextNouns.includes(noun)) score += 1;
    });
    
    return score;
}

/**
 * Handle filter button click
 */
function handleFilter() {
    if (allPosts.length === 0) {
        showError('Please load a JSON file first.');
        return;
    }

    const query = queryInput.value.trim();
    
    if (!query) {
        filteredPosts = [...allPosts];
        matchedSubreddits = [];
        currentQuery = '';
        queryNouns = [];
        filterInfo.classList.remove('active');
        updateStats('file', allPosts.length, filteredPosts.length);
        renderPosts();
        return;
    }

    currentQuery = query;
    queryNouns = extractNouns(query);
    
    if (queryNouns.length === 0) {
        showError('Could not extract meaningful terms from query. Try different words.');
        return;
    }
    
    const allSubreddits = [...new Set(allPosts.map(p => p.subreddit))];
    matchedSubreddits = allSubreddits.filter(subreddit => {
        const subNouns = extractNouns(subreddit);
        return queryNouns.some(qn => 
            subNouns.some(sn => sn.includes(qn) || qn.includes(sn))
        );
    });
    
    const postsWithScores = allPosts.map(post => ({
        post,
        relevance: calculateRelevanceScore(post, queryNouns)
    }));
    
    filteredPosts = postsWithScores
        .filter(item => item.relevance > 0)
        .sort((a, b) => {
            if (b.relevance !== a.relevance) return b.relevance - a.relevance;
            return (b.post.score || 0) - (a.post.score || 0);
        })
        .map(item => item.post);

    updateFilterInfo(query, queryNouns, filteredPosts.length, matchedSubreddits, null);
    updateStats('file', allPosts.length, filteredPosts.length);
    renderPosts();
}

/**
 * Update filter info display
 */
function updateFilterInfo(query, nouns, count, subreddits, filename) {
    filterInfo.classList.add('active');
    
    const nounsHtml = nouns.map(n => `<span class="highlight">${escapeHtml(n)}</span>`).join(', ');
    const subredditHtml = subreddits.length > 0 
        ? `<span class="subreddit-list">${subreddits.slice(0, 10).map(s => `r/${escapeHtml(s)}`).join(', ')}${subreddits.length > 10 ? '...' : ''}</span>`
        : 'None';
    
    const filenameInfo = filename 
        ? `<p>📁 File: <span class="highlight">${escapeHtml(filename)}</span></p>` 
        : '';
    
    filterInfo.innerHTML = `
        ${filenameInfo}
        <p>🔍 Extracted Words: ${nounsHtml}</p>
        <p>📊 Found: <span class="highlight">${count} relevant posts</span> (${allPosts.length} total)</p>
        <p>📁 Matched Subreddits: ${subredditHtml}</p>
    `;
}

/**
 * Handle clear filter button click
 */
function handleClearFilter() {
    queryInput.value = '';
    currentQuery = '';
    matchedSubreddits = [];
    queryNouns = [];
    filteredPosts = [...allPosts];
    filterInfo.classList.remove('active');
    updateStats('file', allPosts.length, filteredPosts.length);
    renderPosts();
}

/**
 * Render posts to the container
 */
function renderPosts() {
    const postsToShow = showFilteredOnly ? filteredPosts : allPosts;
    
    if (postsToShow.length === 0) {
        postsContainer.innerHTML = `
            <div class="empty-state">
                <p>🔍 No posts ${showFilteredOnly ? 'match your search' : 'loaded'}</p>
                <p class="hint">${showFilteredOnly ? 'Try a different query or show all posts' : 'Load a JSON file to view posts'}</p>
            </div>
        `;
        return;
    }

    postsContainer.innerHTML = postsToShow.map((post, index) => createPostCard(post, index)).join('');

    document.querySelectorAll('.post-card').forEach(card => {
        card.addEventListener('click', () => {
            const postId = card.dataset.id;
            const post = allPosts.find(p => p.id === postId);
            if (post) openModal(post);
        });
    });
}

/**
 * Create HTML for a post card
 */
function createPostCard(post, index) {
    const createdDate = formatDate(post.created_utc);
    const flairHtml = post.flair ? `<span class="flair">${escapeHtml(post.flair)}</span>` : '';
    const hasComments = post.comments && post.comments.length > 0;
    const commentCount = hasComments ? post.comments.length : post.num_comments;
    
    // Calculate relevance for highlighting
    const relevance = queryNouns.length > 0 ? calculateRelevanceScore(post, queryNouns) : 0;
    const isRelevant = relevance > 0;
    
    let titleHtml = escapeHtml(post.title);
    if (queryNouns.length > 0) {
        titleHtml = highlightNouns(titleHtml, queryNouns);
    }
    
    const subredditClass = matchedSubreddits.includes(post.subreddit) ? 'subreddit match' : 'subreddit';
    const relevanceBadge = isRelevant && queryNouns.length > 0 ? `<span class="relevance-badge">★${relevance}</span>` : '';
    
    return `
        <div class="post-card ${isRelevant && queryNouns.length > 0 ? 'relevant-post' : ''}" data-id="${post.id}">
            <div class="post-header">
                <div class="post-score">
                    <span class="score-value">${formatNumber(post.score)}</span>
                    <span class="score-label">score</span>
                    ${relevanceBadge}
                </div>
                <div class="post-title">
                    <h3>${titleHtml}</h3>
                    <div class="post-meta">
                        <span class="${subredditClass}">r/${escapeHtml(post.subreddit)}</span>
                        ${flairHtml}
                        <span class="author">by u/${escapeHtml(post.author)}</span>
                        <span>📅 ${createdDate}</span>
                    </div>
                </div>
            </div>
            <div class="post-footer">
                <div class="post-stats">
                    <span>💬 ${formatNumber(commentCount)} comments${hasComments ? ' ✓' : ''}</span>
                    <span>🔗 ${post.is_self ? 'Text Post' : 'Link Post'}</span>
                </div>
                <div class="post-link">
                    <a href="${post.permalink}" target="_blank" onclick="event.stopPropagation()">View on Reddit →</a>
                </div>
            </div>
        </div>
    `;
}

/**
 * Highlight nouns in text
 */
function highlightNouns(text, nouns) {
    let result = text;
    nouns.forEach(noun => {
        const regex = new RegExp(`(${escapeRegex(noun)})`, 'gi');
        result = result.replace(regex, '<span class="match-highlight">$1</span>');
    });
    return result;
}

/**
 * Escape regex special characters
 */
function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Open modal with post details
 */
function openModal(post) {
    const createdDate = formatDate(post.created_utc, true);
    const flairHtml = post.flair ? `<span class="flair">${escapeHtml(post.flair)}</span>` : '';
    const hasComments = post.comments && post.comments.length > 0;
    
    let commentsHtml = '';
    if (hasComments) {
        const totalComments = countAllComments(post.comments);
        commentsHtml = `
            <div class="comments-section">
                <h3>💬 Comments (${totalComments} total, ${post.comments.length} top-level)</h3>
                <div class="comments-list">
                    ${renderComments(post.comments, 0)}
                </div>
            </div>
        `;
    } else {
        commentsHtml = `
            <div class="comments-section comments-empty">
                <p>No comments scraped. <a href="${post.permalink}" target="_blank">View on Reddit</a> to see all comments.</p>
            </div>
        `;
    }
    
    modalBody.innerHTML = `
        <div class="modal-header">
            <h2>${escapeHtml(post.title)}</h2>
            <div class="modal-meta">
                <div class="modal-score">
                    <span class="score-value">${formatNumber(post.score)}</span>
                    <span class="score-label">points</span>
                </div>
                <span class="subreddit">r/${escapeHtml(post.subreddit)}</span>
                ${flairHtml}
                <span>by u/${escapeHtml(post.author)}</span>
                <span>📅 ${createdDate}</span>
            </div>
        </div>
        
        ${post.selftext ? `
            <div class="modal-selftext">${escapeHtml(post.selftext)}</div>
        ` : ''}
        
        ${commentsHtml}
        
        <div class="modal-actions">
            <a href="${post.permalink}" target="_blank" class="btn btn-primary">
                🔗 Open on Reddit
            </a>
            <a href="${post.url}" target="_blank" class="btn btn-secondary">
                ${post.is_self ? '📄 View Post' : '🔗 Open Link'}
            </a>
        </div>
    `;

    postModal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

/**
 * Count all comments including nested replies
 */
function countAllComments(comments) {
    if (!comments) return 0;
    let count = comments.length;
    comments.forEach(c => {
        if (c.replies) count += countAllComments(c.replies);
    });
    return count;
}

/**
 * Render comments recursively
 */
function renderComments(comments, depth) {
    if (!comments || comments.length === 0) return '';
    
    return comments.map(comment => {
        const hasReplies = comment.replies && comment.replies.length > 0;
        const isOp = comment.is_submitter;
        const depthClass = depth > 0 ? `comment-depth-${Math.min(depth, 8)}` : '';
        const opBadge = isOp ? '<span class="op-badge">OP</span>' : '';
        
        return `
            <div class="comment ${depthClass}">
                <div class="comment-header">
                    <span class="comment-author">${opBadge}${escapeHtml(comment.author)}</span>
                    <span class="comment-score">${formatNumber(comment.score)} pts</span>
                    <span class="comment-time">${formatDate(comment.created_utc)}</span>
                </div>
                <div class="comment-body">${escapeHtml(comment.body)}</div>
                ${hasReplies ? `
                    <div class="comment-replies">
                        ${renderComments(comment.replies, depth + 1)}
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

/**
 * Close modal
 */
function closeModal() {
    postModal.classList.remove('active');
    document.body.style.overflow = '';
}

/**
 * Show error message
 */
function showError(message) {
    postsContainer.innerHTML = `
        <div class="empty-state">
            <p>❌ ${escapeHtml(message)}</p>
        </div>
    `;
}

/**
 * Format number with K/M suffix
 */
function formatNumber(num) {
    if (num === null || num === undefined) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

/**
 * Format Unix timestamp to readable date
 */
function formatDate(timestamp, full = false) {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp * 1000);
    const options = full 
        ? { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' }
        : { year: 'numeric', month: 'short', day: 'numeric' };
    return date.toLocaleDateString('en-US', options);
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', init);
