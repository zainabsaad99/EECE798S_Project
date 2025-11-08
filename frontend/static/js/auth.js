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
        window.location.href = result.redirect || "/account";
      } else {
        alert(result.message || "Sign in failed. Please try again.");
      }
    } catch (error) {
      console.error("Error:", error);
      alert("An error occurred. Please try again.");
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
      alert("Passwords do not match");
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
        window.location.href = result.redirect || "/signin";
      } else {
        alert(result.message || "Sign up failed. Please try again.");
      }
    } catch (error) {
      console.error("Error:", error);
      alert("An error occurred. Please try again.");
    }
  });
}
