document.addEventListener("DOMContentLoaded", function () {
    const endTime = new Date("2025-10-01T23:59:59Z").getTime();
    const countdown = setInterval(() => {
        const now = new Date().getTime();
        const distance = endTime - now;

        document.getElementById("days").innerText = Math.floor(distance / (1000 * 60 * 60 * 24)).toString().padStart(2, '0');
        document.getElementById("hours").innerText = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)).toString().padStart(2, '0');
        document.getElementById("minutes").innerText = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60)).toString().padStart(2, '0');
        document.getElementById("seconds").innerText = Math.floor((distance % (1000 * 60)) / 1000).toString().padStart(2, '0');
    }, 1000);
});