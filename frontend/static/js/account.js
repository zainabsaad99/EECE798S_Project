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
// Company Form Handler
const companyForm = document.getElementById("companyForm")
if (companyForm) {
  companyForm.addEventListener("submit", async (e) => {
    e.preventDefault()

    const formData = new FormData(companyForm)
    const linkedinUrl = formData.get("linkedin")
    const websiteUrl = formData.get("website")
    
    // Require LinkedIn
    if (!linkedinUrl || linkedinUrl.trim() === '') {
      showStatus("LinkedIn Profile URL is required to use the LinkedIn Agent feature.", 'error')
      return
    }

    // ⭐ NEW: Require Website
    if (!websiteUrl || websiteUrl.trim() === '') {
      alert("Company Website is required before saving.")
      return
    }

    const data = {
      company: formData.get("company"),
      website: websiteUrl,
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

// JSON Upload Form Handler
const jsonUploadForm = document.getElementById("jsonUploadForm");
if (jsonUploadForm) {
  jsonUploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const fileInput = document.getElementById("jsonFile");
    const file = fileInput.files[0];

    if (!file) {
      alert("Please select a JSON file to upload.");
      return;
    }

    if (!file.name.endsWith(".json")) {
      alert("Only JSON files are allowed.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    const submitBtn = jsonUploadForm.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = "Uploading...";

    try {
      const res = await fetch("/account/upload-json", {
        method: "POST",
        body: formData
      });

      const result = await res.json();

      if (result.success) {
        alert(result.message || "JSON uploaded/updated successfully!");
      } else {
        alert(result.message || "Error uploading JSON.");
      }

    } catch (err) {
      console.error(err);
      alert("An unexpected error occurred.");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = originalText;
      // Optional: reset file input
      fileInput.value = "";
    }
  });
}
