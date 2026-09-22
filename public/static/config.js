(function () {
    var base = '/api';
    if (window.location.protocol === 'file:') {
        base = 'http://localhost:8000/api';
    }
    window.APP_API_BASE = window.APP_API_BASE || base;
})();