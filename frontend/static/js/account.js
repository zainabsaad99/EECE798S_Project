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
      alert("LinkedIn Profile URL is required to use the LinkedIn Agent feature.")
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
