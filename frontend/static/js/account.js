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
  companyForm.addEventListener("submit", (e) => {
    e.preventDefault()

    const formData = new FormData(companyForm)
    const data = {
      company: formData.get("company"),
      website: formData.get("website"),
      linkedin: formData.get("linkedin"),
      industry: formData.get("industry"),
      company_size: formData.get("company_size"),
    }

    updateAccount(data)
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
