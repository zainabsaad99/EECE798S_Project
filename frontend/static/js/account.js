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

// Company Form - Separate button handlers
const companyForm = document.getElementById("companyForm")
// Prevent form submission on Enter key
if (companyForm) {
  companyForm.addEventListener("submit", (e) => {
    e.preventDefault()
  })
}

// Save LinkedIn Button Handler
const saveLinkedInBtn = document.getElementById("saveLinkedInBtn")
if (saveLinkedInBtn && companyForm) {
  saveLinkedInBtn.addEventListener("click", async (e) => {
    e.preventDefault()

    const formData = new FormData(companyForm)
    const linkedinUrl = formData.get("linkedin")
    
    // Require LinkedIn
    if (!linkedinUrl || linkedinUrl.trim() === '') {
      showStatus("LinkedIn Profile URL is required to use the LinkedIn Agent feature.", 'error')
      return
    }

    const data = {
      linkedin: linkedinUrl,
    }

    // Show loading state
    saveLinkedInBtn.disabled = true
    const originalText = saveLinkedInBtn.textContent
    saveLinkedInBtn.textContent = "Saving and analyzing profile..."

    try {
      const res = await fetch("/account", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })
      const result = await res.json()
      
      if (result.success) {
        if (result.linkedin_processed) {
          showStatus("LinkedIn saved! Your LinkedIn profile has been analyzed. You can now use the LinkedIn Agent.", 'success')
        } else {
          showStatus(result.message || "LinkedIn saved successfully!", 'success')
        }
      } else {
        showStatus(result.message || "Error saving LinkedIn", 'error')
      }
    } catch (err) {
      console.error(err)
      showStatus("An unexpected error occurred.", 'error')
    } finally {
      saveLinkedInBtn.disabled = false
      saveLinkedInBtn.textContent = originalText
    }
  })
}

// Save Website Button Handler
const saveWebsiteBtn = document.getElementById("saveWebsiteBtn")
if (saveWebsiteBtn && companyForm) {
  saveWebsiteBtn.addEventListener("click", async (e) => {
    e.preventDefault()

    const formData = new FormData(companyForm)
    const websiteUrl = formData.get("website")
    const companyName = formData.get("company")
    
    // Require Website
    if (!websiteUrl || websiteUrl.trim() === '') {
      showStatus("Company Website is required before saving.", 'error')
      return
    }

    const data = {
      company: companyName,
      website: websiteUrl,
    }

    // Show loading state
    saveWebsiteBtn.disabled = true
    const originalText = saveWebsiteBtn.textContent
    saveWebsiteBtn.textContent = "Saving and extracting website data..."

    try {
      const res = await fetch("/account", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })
      const result = await res.json()
      
      if (result.success) {
        showStatus(result.message || "Website saved and data extracted successfully!", 'success')
      } else {
        showStatus(result.message || "Error saving website", 'error')
      }
    } catch (err) {
      console.error(err)
      showStatus("An unexpected error occurred.", 'error')
    } finally {
      saveWebsiteBtn.disabled = false
      saveWebsiteBtn.textContent = originalText
    }
  })
}

// Save Industry & Company Size Button Handler
const saveIndustryBtn = document.getElementById("saveIndustryBtn")
if (saveIndustryBtn && companyForm) {
  saveIndustryBtn.addEventListener("click", async (e) => {
    e.preventDefault()

    const formData = new FormData(companyForm)
    const industry = formData.get("industry")
    const companySize = formData.get("company_size")

    const data = {
      industry: industry,
      company_size: companySize,
    }

    // Show loading state
    saveIndustryBtn.disabled = true
    const originalText = saveIndustryBtn.textContent
    saveIndustryBtn.textContent = "Saving..."

    try {
      const res = await fetch("/account", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })
      const result = await res.json()
      
      if (result.success) {
        showStatus("Industry and company size saved successfully!", 'success')
      } else {
        showStatus(result.message || "Error saving industry and company size", 'error')
      }
    } catch (err) {
      console.error(err)
      showStatus("An unexpected error occurred.", 'error')
    } finally {
      saveIndustryBtn.disabled = false
      saveIndustryBtn.textContent = originalText
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
