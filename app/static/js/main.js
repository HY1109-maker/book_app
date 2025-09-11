function handleLikeClick(event) {
    // クリックされた要素の最も近い親である .like-section を探す
    const likeSection = event.target.closest('.like-section');

    // もし .like-section の中でクリックが起きた場合のみ、以下の処理を実行
    if (likeSection) {
        event.preventDefault(); // 投稿詳細ページへのリンク遷移をキャンセル

        // .like-section の中から、操作したい要素を具体的に見つける
        const likeBtn = likeSection.querySelector('.like-icon');
        const likesCountSpan = likeSection.querySelector('.likes-count');

        // likeBtnが見つからなければ何もしない（安全対策）
        if (!likeBtn) return;

        const postId = likeBtn.dataset.postId;
        const isLiked = likeBtn.classList.contains('liked');
        const apiUrl = isLiked ? `/unlike/${postId}` : `/like/${postId}`;

        fetch(apiUrl, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ok') {
                    likeBtn.classList.toggle('liked');
                    if (likesCountSpan) {
                        likesCountSpan.textContent = data.likes_count;
                    }
                }
            })
            .catch(error => console.error('Error liking/unliking post:', error));
    }
}

// ページ全体でいいね機能が有効になるように、post-grid全体にイベントリスナーを設定
document.addEventListener('DOMContentLoaded', function() {
    // タイムラインやプロフィールページなど、動的に要素が追加されることを考慮し、
    // イベントリスナーを document 全体に設定する
    document.addEventListener('click', handleLikeClick);
});

document.addEventListener('DOMContentLoaded', function() {
    const profileBtn = document.querySelector('.profile-btn');
    if (profileBtn) {
        const dropdown = profileBtn.nextElementSibling;
        profileBtn.addEventListener('click', function(event) {
            event.stopPropagation();
            dropdown.classList.toggle('show');
        });

        // ドロップダウンの外側をクリックしたら閉じる
        window.addEventListener('click', function(event) {
            if (!profileBtn.contains(event.target)) {
                dropdown.classList.remove('show');
            }
        });
    }
});