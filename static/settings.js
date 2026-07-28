// ===================================================================
// Heslo se overuje na serveru — prompt() jen vyzada vstup a posle ho
// skrytym polem; spravnou hodnotu zna jen app01.py
// ===================================================================
function askPassword() {
    var pwd = prompt("Zadej heslo pro ulozeni nastaveni:");
    if (!pwd) return false;
    document.getElementById("settings-password").value = pwd;
    return true;
}

function readNumber(name) {
    return Number(document.querySelector(`input[name="${name}"]`).value);
}

document.querySelector("#settings-form").addEventListener("submit", function (e) {
    // Heslo — pokud neni spravne, nic se neulozi
    if (!askPassword()) {
        e.preventDefault();
        return;
    }

    const submitter = e.submitter;
    const action = submitter ? submitter.value || "" : "";
    const pairs = [
        { on: "zapni4", off: "vypni4", label: "Podlaha 300W" },
        { on: "zapni2", off: "vypni2", label: "Podlaha 2000W" },
        { on: "zapni3", off: "vypni3", label: "Podlaha 2200W" },
        { on: "zapni_bojler", off: "vypni_bojler", label: "Bojler" },
        { on: "zapni_virivka", off: "vypni_virivka", label: "Virivka" },
        { on: "zapni_rele", off: "vypni_rele", label: "Menic 2" },
    ];

    for (const pair of pairs) {
        const onValue = readNumber(pair.on);
        const offValue = readNumber(pair.off);

        if (onValue <= offValue) {
            e.preventDefault();
            alert(`${pair.label}: zapinaci mez musi byt vyssi nez vypinaci.`);
            return;
        }
    }

    if (action.startsWith("save_profile:")) {
        if (!confirm("Opravdu chcete ulozit zobrazenou konfiguraci do sezonniho profilu?")) {
            e.preventDefault();
        }
        return;
    }

    if (!confirm("Opravdu chcete ulozit aktivni nastaveni?")) {
        e.preventDefault();
    }
});
