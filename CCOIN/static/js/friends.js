document.addEventListener("DOMContentLoaded", () => {
  const referralCode = window.referralCode || "";
  const inviteLink = `https://t.me/CTG_COIN_BOT?start=${referralCode}`;

  document.getElementById('inviteButton').addEventListener('click', () => {
    window.open(`tg://msg?text=${encodeURIComponent(inviteLink)}`, '_blank');
  });

  document.getElementById('copyButton').addEventListener('click', () => {
    navigator.clipboard.writeText(inviteLink).then(() => {
      alert("Invite link copied to clipboard!");
    });
  });
});
