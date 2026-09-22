(function () {
    var base = '';
    if (window.location.protocol === 'file:') {
        base = 'http://localhost:8000';
    }
    window.APP_API_BASE = window.APP_API_BASE || base;
})();
