// Český formát data a času
function updateDateTime() {
    const el = document.getElementById('datetime');
    if (!el) return; // Pokud prvek neexistuje, funkce se tiše ukončí a neshodí zbytek JS
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

    // Pomocná proměnná pro aktuální skupinu (budeme ji přepisovat)
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
        console.log("Nabijeni proudem:", data.chrging);

    } else if (data.dischrging > 0 || data.dischrging2 > 0) {
        // Vybíjení
        group = document.getElementById('flow-menicL-battery');
        if (group) {
            group.classList.add('active');
            group.querySelector('.flow-value').textContent = data.dischrging.toFixed(1) + " A";
        }

        // Tady posíláme animaci na obě větve
        updateFlow('flow-menicL-battery', data.dischrging, 'discharging');
        //updateFlow('flow-menicR-battery', data.dischrging, 'discharging');
        console.log("Vybijeni proudem:", data.dischrging);

    } else {
        // Klidový stav - nula
        // Odstraníme 'active', aby čísla (otazníky) zmizela/zešedla
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
    updateFlow('flow-menicR-podlaha2000', data.heating2, 'standard');
    updateFlow('flow-menicR-podlaha300', data.heating3, 'standard');

    // Toky ze měniče 2 ke spotřebičům
    var virivkaFlow = (data.virivkaStatus === 'ZAP') ? (data.virivkaActualW || data.virivka || 2300) : data.virivkaActualW;
    updateFlow('flow-menicR-virivka', virivkaFlow, 'standard');
}
// Aktualizace jednoho toku
function updateFlow(flowId, power, type) {
    const flow = document.getElementById(flowId);

    // PŘIDAT: Kontrola jestli element existuje
    if (!flow) {
        console.error('Flow element not found:', flowId);
        return; // Ukončit funkci
    }

    const line = flow.querySelector('.flow-line');
    const value = flow.querySelector('.flow-value');

    // Nastav výkon
//    value.textContent = formatPower(power);

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
    // Nejdříve všechno smažeme, ať nevisí staré barvy
    frame.classList.remove('charging', 'discharging', 'alarm');

    // BARVA: Vybíjení (Pokud používáte vaše data.dischrging, která jsou > 0)
    if (data.dischrging > 0) {
        frame.classList.add('discharging');
    }
    // BARVA: Nabíjení (Pokud používáte data.chrging > 0)
    else if (data.chrging > 0) {
        frame.classList.add('charging');
    }

    // ALARM: Napětí (Pokud napětí klesne pod 25V nebo stoupne nad 27.1V)
    if (data.inab_V < 25.0 || data.inab_V > 26.4) {
        frame.classList.add('alarm');
    }
}


    //const batteryFlow = data.batCurrent * data.batVoltage;
    //document.getElementById('batteryFlow').textContent = formatPower(Math.abs(battery_Flow));

    // Spotřebiče
    document.getElementById('dum').querySelector('.power-value').textContent = Math.round(data.load) + ' %';
    document.getElementById('bojler').querySelector('.power-value').textContent = formatPower(data.boiler);
    document.getElementById('podlaha2200').querySelector('.power-value').textContent = formatPower(data.heating1);
    const duvodEl = document.getElementById('podlaha2200Duvod');
    if (duvodEl) duvodEl.textContent = data.podlahovka2200Duvod || '—';
    document.getElementById('podlaha2000').querySelector('.power-value').textContent = formatPower(data.heating2);
    document.getElementById('podlaha300').querySelector('.power-value').textContent = formatPower(data.heating3);
    // Vířivka — VŽDY skutečný odběr (proud0 × 220V), nikdy nominál!
    const virivkaActual = data.virivkaActualW || 0;
    const virivkaOPIon = (data.virivkaOPI || 0) > 0;
    document.getElementById('virivka').querySelector('.power-value').textContent = formatPower(virivkaActual);
    document.getElementById('virivka').querySelector('.power-value').style.color = virivkaOPIon ? '' : '#888';
    const tempEl = document.getElementById('virivkaTemp');
    if (tempEl) {
        tempEl.textContent = (data.virivkaTemp || 0).toFixed(1) + ' °C';
        tempEl.className = 'virivka-temp' + (virivkaActual > 0 ? ' on' : '');
    }

    const menic2Icon = document.querySelector('.menic-right .icon');
    if (menic2Icon) {
        menic2Icon.classList.toggle('icon-alert', Number(data.menic2Enabled) > 0);
    }

    // Aktualizace toků energie
    updateEnergyFlows(data);
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

//----------------------------------------------
/*function updateData() {
    fetch('/data')
        .then(response => response.json())
        .then(data => {
            //console.log("DATA DORAZILA:", data); // <--- A tohle
            updateUI(data);
        });
}  */
//----------------------------------------------
// Režim simulace (nastav na false pro reálná data)
//window.SIMULATE = false;
