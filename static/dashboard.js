// Český formát data a času

var podlahovka2200_lastDuvod = "";
var podlahovka2200_duvodUntil = 0;

function updateDateTime() {
    const el = document.getElementById('datetime');
    if (!el) return;
    const now = new Date();
    const options = {
        weekday: 'long',
        year: 'numeric',
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    };
    document.getElementById('datetime').textContent =
        now.toLocaleDateString('cs-CZ', options);
}


// Formátování výkonu (W/kW)
function formatPower(watts) {
    if (watts === 0) return '0 W';
    return watts >= 1000 ? (watts / 1000).toFixed(1) + ' kW' : Math.round(watts) + ' W';
}

function updateEnergyFlows(data) {
    // Toky z panelů k měničům
    updateFlow('flow-panelL-menicL', data.pvPower1, 'standard');
    updateFlow('flow-panelR-menicR', data.pvPower2, 'standard');

    let group;

    // Toky mezi měniči a baterií
    if (data.chrging > 0 || data.chrging2 > 0) {
        // Nabíjení
        group = document.getElementById('flow-menicL-battery');
        if (group) {
            group.classList.add('active');
            group.querySelector('.flow-value').textContent = data.chrging.toFixed(1) + " A";
        }

        updateFlow('flow-menicL-battery', data.chrging, 'charging');
        updateFlow('flow-menicR-battery', data.chrging2, 'charging');

    } else if (data.dischrging > 0 || data.dischrging2 > 0) {
        // Vybíjení
        group = document.getElementById('flow-menicL-battery');
        if (group) {
            group.classList.add('active');
            group.querySelector('.flow-value').textContent = data.dischrging.toFixed(1) + " A";
        }

        updateFlow('flow-menicL-battery', data.dischrging, 'discharging');

    } else {
        let gL = document.getElementById('flow-menicL-battery');
        let gR = document.getElementById('flow-menicR-battery');
        if(gL) gL.classList.remove('active');
        if(gR) gR.classList.remove('active');

        updateFlow('flow-menicL-battery', 0, 'standard');
        updateFlow('flow-menicR-battery', 0, 'standard');
    }


    // Toky ze měniče 1 ke spotřebičům
    updateFlow('flow-menicL-dum', data.load, 'standard');
    updateFlow('flow-menicL-bojler', data.boiler, 'standard');
    var podlaha2200Flow = data.heating1HasFeedback ? data.heating1Actual : data.heating1;
    updateFlow('flow-menicL-podlaha2200', podlaha2200Flow, 'standard');
    // Podlahovky: animace jen když relé skutečně sepnuto (ESP feedback)
    updateFlow('flow-menicR-podlaha2000', data.podlaha2000_skutecny || 0, 'standard');
    updateFlow('flow-menicR-podlaha300', data.podlaha300_skutecny || 0, 'standard');

    // Toky ze měniče 2 ke spotřebičům
    // Vířivka: modrá animace JEN když je aspoň jedno relé ZAP
    var virivkaFlow = (data.virivkaStatus === 'ZAP') ? (data.virivkaActualW || 2300) : 0;
    updateFlow('flow-menicR-virivka', virivkaFlow, 'standard');
}
// Aktualizace jednoho toku
function updateFlow(flowId, power, type) {
    const flow = document.getElementById(flowId);

    if (!flow) {
        return;
    }

    const line = flow.querySelector('.flow-line');
    const value = flow.querySelector('.flow-value');

    if (power > 0) {
        // Aktivní tok
        flow.classList.add('active');
        line.classList.add('active', type);
        line.classList.remove('charging', 'discharging', 'standard');
        line.classList.add(type);
    } else {
        // Neaktivní tok
        flow.classList.remove('active');
        line.classList.remove('active', 'charging', 'discharging', 'standard');
    }
}

// Aktualizace UI
function updateUI(data) {
    // Panely
    document.getElementById('powerPanelL').textContent = formatPower(data.pvPower1);
    document.getElementById('powerPanelR').textContent = formatPower(data.pvPower2);
    document.getElementById('totalPower').textContent = formatPower(data.pvPower1 + data.pvPower2);

    // Měniče a baterie
    document.getElementById('powerMenicL').textContent = formatPower(data.inv1Power);
    document.getElementById('powerMenicR').textContent = formatPower(data.inv2Power);
    document.getElementById('batteryVoltage').textContent = data.batVoltage.toFixed(1) + ' V';
    document.getElementById('batteryFlow').textContent = `${data.battery_Flow} %`;
    document.getElementById('inab_A').textContent = `${data.inab_A} A`;
    document.getElementById('inab_W').textContent = `${data.inab_W} W`;
    document.getElementById('inab_V').textContent = `${data.inab_V} V`;

const frame = document.getElementById('ina-frame');
if (frame) {
    frame.classList.remove('charging', 'discharging', 'alarm');

    if (data.dischrging > 0) {
        frame.classList.add('discharging');
    }
    else if (data.chrging > 0) {
        frame.classList.add('charging');
    }

    if (data.inab_V < 25.0 || data.inab_V > 26.4) {
        frame.classList.add('alarm');
    }
}

// Bateriový indikátor — plnění šedého pásu odspodu
(function(){
    var v = data.batVoltage || 25;
    var pct = Math.max(0, Math.min(100, (v - 25) / (27 - 25) * 100));
    var c = pct < 30 ? '#e94560' : pct < 60 ? '#f0a500' : '#4ecca3';
    var fill = document.getElementById('battery-fill');
    if (fill) {
        fill.style.height = pct + '%';
        fill.style.background = c;
    }
})();


    // Spotřebiče — DŮM
    document.getElementById('dum').querySelector('.power-value').textContent = Math.round(data.load) + ' %';

    // --- BOJLER ---
    var boilerOPI = data.boiler > 0;
    document.getElementById('bojler').querySelector('.power-value').textContent = formatPower(data.boiler);
    document.getElementById('bojler').querySelector('.power-value').style.color = boilerOPI ? '' : '#888';

    // --- PODLAHA 2200W ---
    var p2200 = data.heating1HasFeedback ? (data.heating1Actual || 0) : data.heating1;
    var p2200OPI = data.heating1 > 0;
    document.getElementById('podlaha2200').querySelector('.power-value').textContent = formatPower(p2200);
    document.getElementById('podlaha2200').querySelector('.power-value').style.color = p2200OPI ? '' : '#888';
    var duvodEl = document.getElementById('podlaha2200Duvod');
    if (duvodEl) {
        var now = Date.now();
        var cur = data.podlahovka2200Duvod || '';
        var opiChce = data.heating1 > 0;
        var espTopi = data.heating1HasFeedback ? (data.heating1Actual > 0) : opiChce;
        var ukazDuvod = opiChce && !espTopi && cur;

        if (cur && cur !== podlahovka2200_lastDuvod) {
            podlahovka2200_lastDuvod = cur;
            podlahovka2200_duvodUntil = now + 5000;
        }
        if (now < podlahovka2200_duvodUntil || ukazDuvod) {
            duvodEl.textContent = cur;
            duvodEl.className = 'podlahovka-duvod';
        } else {
            var tv = data.podlahovka2200TempVstup;
            var to = data.podlahovka2200TempVystup;
            // Když ESP offline nebo teploty nedorazily → prázdno
            if (!data.podlahovka2200_online || (tv === undefined && to === undefined)) {
                duvodEl.textContent = '\u2014';
                duvodEl.className = 'podlahovka-duvod';
            } else {
                duvodEl.textContent = 'in' + (tv || 0).toFixed(1) + ' | out' + (to || 0).toFixed(1);
                duvodEl.className = 'podlahovka-duvod podlahovka-teplota';
            }
        }
    }

    // --- PODLAHA 2000W ---
    var p2000OPI = data.podlaha2000_prikaz > 0;
    document.getElementById('podlaha2000').querySelector('.power-value').textContent = formatPower(data.podlaha2000_prikaz);
    document.getElementById('podlaha2000').querySelector('.power-value').style.color = p2000OPI ? '' : '#888';

    // --- PODLAHA 300W ---
    var p300OPI = data.podlaha300_prikaz > 0;
    document.getElementById('podlaha300').querySelector('.power-value').textContent = formatPower(data.podlaha300_prikaz);
    document.getElementById('podlaha300').querySelector('.power-value').style.color = p300OPI ? '' : '#888';

    // --- VÍŘIVKA ---
    const virivkaActual = data.virivkaActualW || 0;
    const virivkaOPIon = (data.virivkaOPI || 0) > 0 || (data.virivka2OPI || 0) > 0;
    document.getElementById('virivka').querySelector('.power-value').textContent = formatPower(virivkaActual);
    document.getElementById('virivka').querySelector('.power-value').style.color = virivkaOPIon ? '' : '#888';
    const tempEl = document.getElementById('virivkaTemp');
    if (tempEl) {
        tempEl.textContent = (data.virivkaTemp || 0).toFixed(1) + ' °C';
        tempEl.className = 'virivka-temp' + (virivkaActual > 0 ? ' on' : '');
    }

    const menic2Icon = document.querySelector('.menic-right .icon');
    if (menic2Icon) {
        menic2Icon.classList.toggle('inactive', !data.menic2_online);
    }

    // Aktualizace toků energie
    updateEnergyFlows(data);
    // --- ESP online/offline signalizace + odkazy na subdomény ---
    var isProduction = window.location.hostname.indexOf('fv-peter') !== -1;

    document.querySelectorAll('.cell.spotrebic a.icon-link').forEach(function(a) {
        var subdomain = a.dataset.subdomain;
        var localIp = a.dataset.localIp;
        var device = a.dataset.device;

        a.href = isProduction
            ? 'https://' + subdomain + '.fv-peter.cz'
            : 'http://' + localIp;

        var onlineKey = device + '_online';
        var img = a.querySelector('.icon');
        if (img && onlineKey in data) {
            img.classList.toggle('inactive', !data[onlineKey]);
        }
    });
}
//----------------------------------------------

document.addEventListener('click', function(e) {
    const container = document.querySelector('.container');
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    console.log(`X: ${Math.round(x)}, Y: ${Math.round(y)}`);
});
//-----------------------------------------------
 //Hlavní funkce
function updateData() {
    fetch('/data')
        .then(response => response.json())
        .then(data => updateUI(data));
}
// Inicializace
updateDateTime();
setInterval(updateDateTime, 1000);
setInterval(updateData, 2000);
updateData();
