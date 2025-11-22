async function updateAccount(data) {
  try {
    const res = await fetch("/account", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    })
    const result = await res.json()
    alert(result.message || (result.success ? "Saved!" : "Error"))
  } catch (err) {
    console.error(err)
    alert("An unexpected error occurred.")
  }
}

// Profile Form Handler
const profileForm = document.getElementById("profileForm")
if (profileForm) {
  profileForm.addEventListener("submit", (e) => {
    e.preventDefault()

    const formData = new FormData(profileForm)
    const data = {
      full_name: formData.get("full_name"),
      phone: formData.get("phone"),
      job_title: formData.get("job_title"),
    }

    updateAccount(data)
  })
}

// Company Form Handler
const companyForm = document.getElementById("companyForm")
if (companyForm) {
  companyForm.addEventListener("submit", async (e) => {
    e.preventDefault()

    const formData = new FormData(companyForm)
    const linkedinUrl = formData.get("linkedin")
    
    // Check if LinkedIn URL is provided and required
    if (!linkedinUrl || linkedinUrl.trim() === '') {
      alert("LinkedIn Profile URL is required to use the LinkedIn Agent feature.")
      return
    }

    const data = {
      company: formData.get("company"),
      website: formData.get("website"),
      linkedin: linkedinUrl,
      industry: formData.get("industry"),
      company_size: formData.get("company_size"),
    }

    // Show loading state
    const submitBtn = companyForm.querySelector('button[type="submit"]')
    const originalText = submitBtn.textContent
    submitBtn.disabled = true
    submitBtn.textContent = "Saving and analyzing profile..."

    try {
      const res = await fetch("/account", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })
      const result = await res.json()
      
      if (result.success) {
        if (result.linkedin_processed) {
          alert("Profile saved! Your LinkedIn profile has been analyzed. You can now use the LinkedIn Agent.")
        } else {
          alert(result.message || "Profile saved!")
        }
      } else {
        alert(result.message || "Error saving profile")
      }
    } catch (err) {
      console.error(err)
      alert("An unexpected error occurred.")
    } finally {
      submitBtn.disabled = false
      submitBtn.textContent = originalText
    }
  })
}

// Goals Form Handler
const goalsForm = document.getElementById("goalsForm")
if (goalsForm) {
  goalsForm.addEventListener("submit", (e) => {
    e.preventDefault()

    const formData = new FormData(goalsForm)
    const data = {
      marketing_goals: formData.get("marketing_goals"),
    }

    updateAccount(data)
  })
}
