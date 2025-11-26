// Status message handler
function showStatus(message, type = 'info') {
  let statusContainer = document.getElementById('statusMessages');
  if (!statusContainer) {
    // Create status container if it doesn't exist
    statusContainer = document.createElement('div');
    statusContainer.id = 'statusMessages';
    statusContainer.className = 'status-messages';
    const firstForm = document.querySelector('.account-form');
    if (firstForm) {
      firstForm.parentNode.insertBefore(statusContainer, firstForm);
    } else {
      document.querySelector('.account-main')?.appendChild(statusContainer);
    }
  }
  
  const messageEl = document.createElement('div');
  messageEl.className = `status-message status-${type}`;
  messageEl.textContent = message;
  
  statusContainer.innerHTML = ''; // Clear previous messages
  statusContainer.appendChild(messageEl);
  
  // Auto-remove success messages after 3 seconds
  if (type === 'success') {
    setTimeout(() => {
      messageEl.style.opacity = '0';
      messageEl.style.transform = 'translateY(-5px)';
      setTimeout(() => {
        if (messageEl.parentNode) {
          messageEl.parentNode.removeChild(messageEl);
        }
      }, 300);
    }, 3000);
  }
}

async function updateAccount(data) {
  try {
    const res = await fetch("/account", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    })
    const result = await res.json()
    showStatus(result.message || (result.success ? "Saved!" : "Error"), result.success ? 'success' : 'error')
  } catch (err) {
    console.error(err)
    showStatus("An unexpected error occurred.", 'error')
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
      showStatus("LinkedIn Profile URL is required to use the LinkedIn Agent feature.", 'error')
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
          showStatus("Profile saved! Your LinkedIn profile has been analyzed. You can now use the LinkedIn Agent.", 'success')
        } else {
          showStatus(result.message || "Profile saved!", 'success')
        }
      } else {
        showStatus(result.message || "Error saving profile", 'error')
      }
    } catch (err) {
      console.error(err)
      showStatus("An unexpected error occurred.", 'error')
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
