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

    console.log("🔵 [SIGNIN] Sending request to /signin");
    try {
      const response = await fetch("/signin", {
        method: "POST",
        credentials: "include", // ensures session cookie is stored
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      console.log("🔵 [SIGNIN] Response received:", {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok
      });

      const result = await response.json();
      console.log("🔵 [SIGNIN] Response JSON:", result);

      if (result.success) {
        console.log("✅ [SIGNIN] Success! Redirecting...");
        showStatus("Sign in successful! Redirecting...", "success");
        setTimeout(() => {
          window.location.href = result.redirect || "/home";
        }, 500);
      } else {
        console.error("❌ [SIGNIN] Failed:", result.message || "Unknown error");
        showStatus(result.message || "Sign in failed. Please try again.", "error");
      }
    } catch (error) {
      console.error("❌ [SIGNIN] Exception caught:", error);
      console.error("❌ [SIGNIN] Error details:", {
        name: error.name,
        message: error.message,
        stack: error.stack
      });
      showStatus(`An error occurred: ${error.message}. Please check the console for details.`, "error");
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
    console.log("🔵 [SIGNUP] Form submitted");

    const formData = new FormData(signupForm);
    const password = formData.get("password");
    const confirmPassword = formData.get("confirm_password");

    console.log("🔵 [SIGNUP] Form data extracted:", {
      full_name: formData.get("full_name"),
      email: formData.get("email"),
      password_length: password ? password.length : 0,
      confirm_password_length: confirmPassword ? confirmPassword.length : 0
    });

    if (password !== confirmPassword) {
      console.error("❌ [SIGNUP] Passwords do not match");
      showStatus("Passwords do not match", "error");
      return;
    }

    const data = {
      full_name: formData.get("full_name"),
      email: formData.get("email"),
      password: password,
    };

    console.log("🔵 [SIGNUP] Sending request to /signup with data:", {
      ...data,
      password: "[REDACTED]"
    });

    try {
      const response = await fetch("/signup", {
        method: "POST",
        credentials: "include", // keep session consistent
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      console.log("🔵 [SIGNUP] Response received:", {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        headers: Object.fromEntries(response.headers.entries())
      });

      // Check if response is JSON
      let result;
      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        result = await response.json();
        console.log("🔵 [SIGNUP] Response JSON:", result);
      } else {
        const text = await response.text();
        console.error("❌ [SIGNUP] Response is not JSON:", text);
        showStatus(`Server error: ${response.status} ${response.statusText}`, "error");
        return;
      }

      if (result.success) {
        console.log("✅ [SIGNUP] Success! Redirecting...");
        showStatus("Account created successfully! Redirecting to sign in...", "success");
        setTimeout(() => {
          window.location.href = result.redirect || "/signin";
        }, 1500);
      } else {
        console.error("❌ [SIGNUP] Failed:", result.message || "Unknown error");
        showStatus(result.message || "Sign up failed. Please try again.", "error");
      }
    } catch (error) {
      console.error("❌ [SIGNUP] Exception caught:", error);
      console.error("❌ [SIGNUP] Error details:", {
        name: error.name,
        message: error.message,
        stack: error.stack
      });
      showStatus(`An error occurred: ${error.message}. Please check the console for details.`, "error");
    }
  });
}
