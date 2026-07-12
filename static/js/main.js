// main.js — students will add JavaScript here as features are built

document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".txn-delete-form").forEach(function (form) {
        form.addEventListener("submit", function (e) {
            if (!confirm("Delete this expense? This can't be undone.")) {
                e.preventDefault();
            }
        });
    });
});
