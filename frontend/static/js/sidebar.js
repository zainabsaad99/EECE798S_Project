// Sidebar toggle functionality
const sidebar = document.getElementById("sidebar")
const sidebarToggle = document.getElementById("sidebarToggle")
const sidebarOverlay = document.getElementById("sidebarOverlay")
const mobileMenuBtn = document.getElementById("mobileMenuBtn")

function toggleSidebar() {
  sidebar.classList.toggle("open")
  sidebarOverlay.classList.toggle("active")
}

// Mobile menu button
if (mobileMenuBtn) {
  mobileMenuBtn.addEventListener("click", toggleSidebar)
}

// Sidebar close button
if (sidebarToggle) {
  sidebarToggle.addEventListener("click", toggleSidebar)
}

// Overlay click to close
if (sidebarOverlay) {
  sidebarOverlay.addEventListener("click", toggleSidebar)
}

// Close sidebar when clicking a link on mobile
const sidebarLinks = document.querySelectorAll(".sidebar-link")
sidebarLinks.forEach((link) => {
  link.addEventListener("click", () => {
    if (window.innerWidth <= 1024) {
      toggleSidebar()
    }
  })
})
