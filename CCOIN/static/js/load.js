
window.onload = function () {
    const progress = document.getElementById("progress");
    const congrats = document.getElementById("congrats");


    setTimeout(() => {
        progress.style.width = "100%";
    }, 100);

    setTimeout(() => {
        congrats.style.opacity = 1;
    }, 2200);

    setTimeout(() => {
        window.location.href = "/home";
    }, 5000);
};

