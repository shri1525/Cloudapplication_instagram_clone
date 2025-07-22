
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js";
import { getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-auth.js";

const firebaseConfig = {
    apiKey: "AIzaSyA85atwL6vPc7oOHZedxN6FgkBagcfYq4I",
    authDomain: "caplab-81737.firebaseapp.com",
    projectId: "caplab-81737",
    storageBucket: "caplab-81737.appspot.com",
    messagingSenderId: "533257203237",
    appId: "1:533257203237:web:b5b1079750e5aa5ce759cc"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

function updateUI(cookie) {
    const token = parseCookieToken(cookie);
    const loginBox = document.getElementById("login-box");
    const signOutBtn = document.getElementById("sign-out");

    if (loginBox && signOutBtn) {
        loginBox.hidden = token.length > 0;
        signOutBtn.hidden = token.length === 0;
    }
}

function parseCookieToken(cookie) {
    if (!cookie) return "";
    const pairs = cookie.split(';');
    for (const pair of pairs) {
        const [key, value] = pair.split('=');
        if (key.trim() === "token") return value;
    }
    return "";
}

window.addEventListener("load", function () {
    updateUI(document.cookie);

    // Signup
    document.getElementById("sign-up")?.addEventListener("click", function () {
        const email = document.getElementById("email").value;
        const password = document.getElementById("password").value;

        createUserWithEmailAndPassword(auth, email, password)
            .then((userCredential) => {
                console.log("✅ User created, getting token...");
                return userCredential.user.getIdToken().then((token) => {
                    document.cookie = "token=" + token + ";path=/;SameSite=Strict";

                    // Register user in Firestore
                    console.log("📡 Sending user to /register-user...");
                    return fetch("/register-user", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": "Bearer " + token
                        },
                        body: JSON.stringify({
                            uid: userCredential.user.uid,
                            email: userCredential.user.email
                        })
                    }).then(res => {
                        console.log("✅ /register-user response:", res.status);
                        if (!res.ok) {
                            throw new Error("Failed to register user in backend");
                        }
                        return res;
                    });
                });
            })
            .then(() => {
                console.log("🔁 Redirecting to / after signup...");
                window.location.href = "/";
            })
            .catch((error) => {
                console.error("❌ Sign-up error:", error.code, error.message);
                alert("Sign-up failed: " + error.message);
            });
    });

    // Login
    document.getElementById("login")?.addEventListener("click", function () {
        const email = document.getElementById("email").value;
        const password = document.getElementById("password").value;

        signInWithEmailAndPassword(auth, email, password)
            .then((userCredential) => {
                return userCredential.user.getIdToken().then((token) => {
                    document.cookie = "token=" + token + ";path=/;SameSite=Strict";
                    window.location.href = "/";
                });
            })
            .catch((error) => {
                console.error("Login error:", error.code, error.message);
                alert("Login failed: " + error.message);
            });
    });

    // Logout
    document.getElementById("sign-out")?.addEventListener("click", function () {
        signOut(auth)
            .then(() => {
                document.cookie = "token=;path=/;SameSite=Strict";
                window.location.href = "/";
            })
            .catch((error) => {
                console.error("Sign-out error:", error);
            });
    });
});
