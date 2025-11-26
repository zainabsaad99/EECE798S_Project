// ------------------
// STATUS MESSAGE HANDLER
// ------------------
function showStatus(message, type = 'info') {
  const statusMessages = document.getElementById('statusMessages');
  if (!statusMessages) return;
  
  // Clear existing messages
  statusMessages.innerHTML = '';
  
  const messageEl = document.createElement('div');
  messageEl.className = `status-message status-${type}`;
  messageEl.textContent = message;
  
  statusMessages.appendChild(messageEl);
  
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

// ------------------
// SIGN IN HANDLER
// ------------------
const signinForm = document.getElementById("signinForm");
if (signinForm) {
  signinForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(signinForm);
    const data = {
      email: formData.get("email"),
      password: formData.get("password"),
      remember: formData.get("remember") === "on",
    };

    try {
      const response = await fetch("/signin", {
        method: "POST",
        credentials: "include", // ensures session cookie is stored
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      const result = await response.json();

      if (result.success) {
        showStatus("Sign in successful! Redirecting...", "success");
        setTimeout(() => {
          window.location.href = result.redirect || "/home";
        }, 500);
      } else {
        showStatus(result.message || "Sign in failed. Please try again.", "error");
      }
    } catch (error) {
      console.error("Error:", error);
      showStatus("An error occurred. Please try again.", "error");
    }
  });
}

// ------------------
// SIGN UP HANDLER
// ------------------
const signupForm = document.getElementById("signupForm");
if (signupForm) {
  signupForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(signupForm);
    const password = formData.get("password");
    const confirmPassword = formData.get("confirm_password");

    if (password !== confirmPassword) {
      showStatus("Passwords do not match", "error");
      return;
    }

    const data = {
      full_name: formData.get("full_name"),
      email: formData.get("email"),
      password: password,
    };

    try {
      const response = await fetch("/signup", {
        method: "POST",
        credentials: "include", // keep session consistent
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      const result = await response.json();

      if (result.success) {
        showStatus("Account created successfully! Redirecting to sign in...", "success");
        setTimeout(() => {
          window.location.href = result.redirect || "/signin";
        }, 1500);
      } else {
        showStatus(result.message || "Sign up failed. Please try again.", "error");
      }
    } catch (error) {
      console.error("Error:", error);
      showStatus("An error occurred. Please try again.", "error");
    }
  });
}
