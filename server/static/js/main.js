// Toggle navigation bar
function toggleNav() {
  var nav = document.getElementById("nav");
  if (nav.className === "navigation") {
    nav.className += " responsive";
  } else {
    nav.className = "navigation";
  }
}