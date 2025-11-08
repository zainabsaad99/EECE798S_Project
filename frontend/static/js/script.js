// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
  anchor.addEventListener("click", function (e) {
    e.preventDefault()
    const target = document.querySelector(this.getAttribute("href"))
    if (target) {
      const headerOffset = 64
      const elementPosition = target.getBoundingClientRect().top
      const offsetPosition = elementPosition + window.pageYOffset - headerOffset

      window.scrollTo({
        top: offsetPosition,
        behavior: "smooth",
      })
    }
  })
})

// Add scroll effect to header
let lastScroll = 0
const header = document.querySelector(".header")

window.addEventListener("scroll", () => {
  const currentScroll = window.pageYOffset

  if (currentScroll <= 0) {
    header.style.boxShadow = "none"
  } else {
    header.style.boxShadow = "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
  }

  lastScroll = currentScroll
})

// Add animation on scroll for cards
const observerOptions = {
  threshold: 0.1,
  rootMargin: "0px 0px -50px 0px",
}

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = "1"
      entry.target.style.transform = "translateY(0)"
    }
  })
}, observerOptions)

// Observe all cards
document.querySelectorAll(".feature-card, .workflow-card, .stat-item").forEach((card) => {
  card.style.opacity = "0"
  card.style.transform = "translateY(20px)"
  card.style.transition = "opacity 0.6s ease, transform 0.6s ease"
  observer.observe(card)
})

// Button hover effects with arrow animation
document.querySelectorAll(".btn-primary").forEach((button) => {
  button.addEventListener("mouseenter", function () {
    const arrow = this.querySelector("svg")
    if (arrow) {
      arrow.style.transform = "translateX(4px)"
    }
  })

  button.addEventListener("mouseleave", function () {
    const arrow = this.querySelector("svg")
    if (arrow) {
      arrow.style.transform = "translateX(0)"
    }
  })
})
