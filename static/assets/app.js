// Fixit Pro demo: contact form handling (vanilla JS, no dependencies).
(function () {
  "use strict";

  var form = document.getElementById("lead-form");
  if (!form) return;

  var btn = document.getElementById("submit-btn");
  var spinner = btn.querySelector(".spinner");
  var label = btn.querySelector(".btn-label");
  var alertBox = document.getElementById("form-alert");
  var success = document.getElementById("form-success");
  var demoNote = document.getElementById("demo-note");
  var message = document.getElementById("message");
  var counter = document.getElementById("message-count");
  var FIELDS = ["name", "phone", "service", "message"];

  // Mirror the server rules so most mistakes are caught before a request.
  function validate(data) {
    var errors = {};
    var name = data.name.trim().replace(/\s+/g, " ");
    var digits = data.phone.replace(/\D/g, "");
    if (name.length < 2) errors.name = "Please enter your name.";
    else if (name.length > 60) errors.name = "This field is too long.";
    else if (/\d/.test(name)) errors.name = "Name should not contain digits.";
    if (!/^\+?[0-9\s\-().]{7,20}$/.test(data.phone.trim()) || digits.length < 7 || digits.length > 15)
      errors.phone = "Enter a valid phone number, e.g. +1 555 123 4567.";
    if (!data.service) errors.service = "Choose a service from the list.";
    if (data.message.length > 1000) errors.message = "This field is too long.";
    return errors;
  }

  function setFieldError(field, msg) {
    var input = document.getElementById(field);
    var err = document.getElementById(field + "-error");
    if (!input || !err) return;
    if (msg) {
      input.setAttribute("aria-invalid", "true");
      err.textContent = msg;
      err.hidden = false;
    } else {
      input.removeAttribute("aria-invalid");
      err.textContent = "";
      err.hidden = true;
    }
  }

  function showErrors(errors) {
    FIELDS.forEach(function (f) { setFieldError(f, errors[f]); });
    var first = FIELDS.filter(function (f) { return errors[f]; })[0];
    if (first) document.getElementById(first).focus();
  }

  function showAlert(msg) {
    alertBox.textContent = msg || "";
    alertBox.classList.toggle("hidden", !msg);
  }

  function setLoading(on) {
    btn.disabled = on;
    btn.setAttribute("aria-busy", on ? "true" : "false");
    btn.classList.toggle("opacity-80", on);
    btn.classList.toggle("cursor-wait", on);
    spinner.classList.toggle("hidden", !on);
    label.textContent = on ? "Sending…" : "Send my request";
  }

  // form.elements, not form.name: "name" would hit the form's own attribute.
  function collect() {
    var el = form.elements;
    return {
      name: el.namedItem("name").value,
      phone: el.namedItem("phone").value,
      service: el.namedItem("service").value,
      message: el.namedItem("message").value,
      website: el.namedItem("website").value
    };
  }

  message.addEventListener("input", function () {
    counter.textContent = message.value.length + " / 1000";
  });

  // Clear a field's error as soon as the user edits it.
  FIELDS.forEach(function (f) {
    var el = document.getElementById(f);
    el.addEventListener(f === "service" ? "change" : "input", function () {
      if (el.getAttribute("aria-invalid")) setFieldError(f, "");
    });
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    showAlert("");
    var data = collect();
    var errors = validate(data);
    if (Object.keys(errors).length) {
      showErrors(errors);
      return;
    }
    showErrors({});
    setLoading(true);

    var controller = "AbortController" in window ? new AbortController() : null;
    var timer = controller && setTimeout(function () { controller.abort(); }, 15000);

    fetch("/api/lead", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(data),
      signal: controller ? controller.signal : undefined
    })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (body) {
          return { status: res.status, body: body };
        });
      })
      .then(function (r) {
        if (r.status === 200 && r.body.ok) {
          form.reset();
          counter.textContent = "0 / 1000";
          form.classList.add("hidden");
          demoNote.classList.toggle("hidden", !r.body.demo);
          success.classList.remove("hidden");
          success.focus();
          return;
        }
        if (r.status === 422 && r.body.fields) showErrors(r.body.fields);
        showAlert(r.body.error || "Something went wrong. Please try again or call us.");
      })
      .catch(function () {
        showAlert("Network problem. Check your connection and try again, or call (555) 0100.");
      })
      .then(function () {
        if (timer) clearTimeout(timer);
        setLoading(false);
      });
  });

  document.getElementById("send-another").addEventListener("click", function () {
    success.classList.add("hidden");
    form.classList.remove("hidden");
    document.getElementById("name").focus();
  });
})();
