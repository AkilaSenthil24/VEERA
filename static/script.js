/* FindBack-Campus — Interactive Client Behaviors */

document.addEventListener("DOMContentLoaded", () => {
  // 1. Mobile Navigation Drawer Toggle
  const navToggle = document.getElementById("nav-toggle");
  const mobileDrawer = document.getElementById("mobile-drawer");
  if (navToggle && mobileDrawer) {
    navToggle.addEventListener("click", () => {
      const isOpen = mobileDrawer.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", String(isOpen));
    });
  }

  // 2. Dismissible Flash Alerts
  document.querySelectorAll("[data-dismiss-alert]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const alertBox = btn.closest(".alert");
      if (alertBox) {
        alertBox.remove();
      }
    });
  });

  // 3. Password Visibility Toggle
  document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-toggle-password");
      const input = document.getElementById(targetId);
      if (!input) return;

      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      btn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
      btn.setAttribute("aria-pressed", String(!showing));

      const eyeOpen = btn.querySelector("[data-eye-open]");
      const eyeClosed = btn.querySelector("[data-eye-closed]");
      if (eyeOpen && eyeClosed) {
        eyeOpen.style.display = showing ? "inline" : "none";
        eyeClosed.style.display = showing ? "none" : "inline";
      }
    });
  });

  // 4. Image Upload Preview & Client-Side Size/Type Guard
  const imageInput = document.getElementById("item-image-input");
  const previewImg = document.getElementById("item-image-preview");
  const imageFeedback = document.getElementById("image-upload-feedback");
  if (imageInput && previewImg) {
    imageInput.addEventListener("change", () => {
      const file = imageInput.files && imageInput.files[0];
      if (!file) {
        previewImg.classList.remove("visible");
        previewImg.removeAttribute("src");
        if (imageFeedback) imageFeedback.textContent = "";
        return;
      }

      const validTypes = ["image/png", "image/jpeg", "image/webp", "image/gif"];
      if (!validTypes.includes(file.type)) {
        if (imageFeedback) {
          imageFeedback.textContent = "Unsupported file type. Please choose PNG, JPG, WEBP, or GIF.";
          imageFeedback.style.color = "#B91C1C";
        }
        imageInput.value = "";
        previewImg.classList.remove("visible");
        return;
      }

      if (file.size > 5 * 1024 * 1024) {
        if (imageFeedback) {
          imageFeedback.textContent = "File exceeds 5 MB limit. Please select a smaller image.";
          imageFeedback.style.color = "#B91C1C";
        }
        imageInput.value = "";
        previewImg.classList.remove("visible");
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target && typeof event.target.result === "string") {
          previewImg.src = event.target.result;
          previewImg.classList.add("visible");
          if (imageFeedback) {
            imageFeedback.textContent = `Selected: ${file.name}`;
            imageFeedback.style.color = "#475569";
          }
        }
      };
      reader.readAsDataURL(file);
    });
  }

  // 5. Custom Location Toggle on Report Forms
  const locationSelect = document.getElementById("location-select");
  const customLocationWrap = document.getElementById("custom-location-wrap");
  if (locationSelect && customLocationWrap) {
    const syncCustomLocation = () => {
      const isOther = locationSelect.value === "Other";
      customLocationWrap.style.display = isOther ? "flex" : "none";
      const customInput = customLocationWrap.querySelector("input");
      if (customInput) {
        customInput.required = isOther;
      }
    };
    locationSelect.addEventListener("change", syncCustomLocation);
    syncCustomLocation();
  }

  // 6. Client-Side Confirm Password Check on Register Form
  const registerForm = document.getElementById("register-form");
  if (registerForm) {
    const passwordInput = document.getElementById("password");
    const confirmInput = document.getElementById("confirm_password");
    const matchHint = document.getElementById("password-match-hint");

    const checkMatch = () => {
      if (!passwordInput || !confirmInput || !matchHint) return;
      if (!confirmInput.value) {
        matchHint.textContent = "";
        confirmInput.setCustomValidity("");
        return;
      }
      if (passwordInput.value !== confirmInput.value) {
        matchHint.textContent = "Passwords do not match.";
        matchHint.style.color = "#B91C1C";
        confirmInput.setCustomValidity("Passwords do not match.");
      } else {
        matchHint.textContent = "Passwords match.";
        matchHint.style.color = "#15803D";
        confirmInput.setCustomValidity("");
      }
    };

    if (passwordInput && confirmInput) {
      passwordInput.addEventListener("input", checkMatch);
      confirmInput.addEventListener("input", checkMatch);
    }
  }

  // 7. Owner Edit Item Panel Toggle on Item Details
  const toggleEditBtn = document.getElementById("toggle-edit-panel");
  const editPanel = document.getElementById("edit-item-panel");
  if (toggleEditBtn && editPanel) {
    toggleEditBtn.addEventListener("click", () => {
      const isHidden = editPanel.style.display === "none" || !editPanel.style.display;
      editPanel.style.display = isHidden ? "block" : "none";
      toggleEditBtn.setAttribute("aria-expanded", String(isHidden));
    });
  }

  // 8. Delete Confirmation Inline Guard (No window.confirm/alert)
  const deleteStartBtn = document.getElementById("delete-start-btn");
  const deleteConfirmBox = document.getElementById("delete-confirm-box");
  const deleteCancelBtn = document.getElementById("delete-cancel-btn");
  if (deleteStartBtn && deleteConfirmBox && deleteCancelBtn) {
    deleteStartBtn.addEventListener("click", () => {
      deleteStartBtn.style.display = "none";
      deleteConfirmBox.style.display = "inline-flex";
    });
    deleteCancelBtn.addEventListener("click", () => {
      deleteConfirmBox.style.display = "none";
      deleteStartBtn.style.display = "inline-flex";
    });
  }
});
