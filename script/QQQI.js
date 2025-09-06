const buckets = [
    { id: 'options', prefix: '../data/QQQI-Files/QQQI_Options_-_Index_' },
    { id: 'cash',    prefix: '../data/QQQI-Files/QQQI_Cash_' },
    { id: 'stocks',  prefix: '../data/QQQI-Files/QQQI_Stocks_' }
];

const dateSelect = document.getElementById("dateSelect");
const updateButton = document.getElementById("updateIndex");
const userIndexInput = document.getElementById("userIndex");

// --- Load available dates ---
fetch("../data/QQQI-Files/available_dates.json")
    .then(res => res.json())
    .then(data => {
        data.dates.forEach(date => {
            const opt = document.createElement("option");
            opt.value = date;
            opt.textContent = date;
            dateSelect.appendChild(opt);
        });

        dateSelect.value = data.dates[data.dates.length - 1];
        loadTables(dateSelect.value);
    })
    .catch(err => console.error("Failed to load available_dates.json:", err));

dateSelect.addEventListener("change", () => {
    loadTables(dateSelect.value);
});

// --- Load table JSON ---
function loadTables(date) {
    const timestamp = new Date().getTime();
    buckets.forEach(bucket => {
        const file = `${bucket.prefix}${date}.json?ts=${timestamp}`;
        fetch(file)
            .then(res => res.json())
            .then(data => renderTable(bucket.id, data))
            .catch(err => console.error(`Failed to load ${file}:`, err));
    });
}

// --- Render table ---
function renderTable(bucketId, data) {
    const tbody = document.querySelector(`#${bucketId}-table tbody`);
    tbody.innerHTML = "";
    let totalWeight = 0;
    const today = new Date();

    if (!data || data.length === 0) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = bucketId === 'options' ? 9 : 2;
        td.textContent = "No records available";
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    data.forEach(item => {
        const tr = document.createElement('tr');

        if(bucketId === 'options') {
            const [year, month, day] = item.Expiry_Date.split('-');
            const expiryDate = new Date(`${year}-${month}-${day}`);
            const displayDate = `${day}/${month}/${year}`;

            // Trading Days to Expiration
            const tdte = Math.max(0, Math.round((expiryDate - today) / (1000*60*60*24) * 5/7));

            const strike = Number(item.Strike_Price);
            const opening = Number(item.OpeningPrice);
            const contracts = Number(item.Contracts);
            const totalBaseMV = Number(item.TotalBaseMV);

            // Upside %
            const upside = (strike - opening) / opening * 100;

            let status = '', statusClass = '', forgoneGains = 0;
            if(upside < 0){
                status = 'ITM';
                statusClass = 'itm';
                // 100 shares per contract, % of total base MV
                forgoneGains = ((opening - strike) * 100 * contracts) / totalBaseMV * 100;
            } else {
                status = 'OTM';
                statusClass = 'otm';
                forgoneGains = 0;
            }

            tr.innerHTML = `
                <td>${item.StockTicker}</td>
                <td>${parseFloat(item.Weightings).toFixed(2)}%</td>
                <td data-value="${item.Expiry_Date}">${displayDate}</td>
                <td>${tdte}</td>
                <td>${strike.toLocaleString()}</td>
                <td>${opening.toFixed(2)}</td>
                <td>${upside.toFixed(2)}%</td>
                <td class="${statusClass}">${status}</td>
                <td>${forgoneGains.toFixed(2)}%</td>
                <td style="display:none;">${contracts}</td>
                <td style="display:none;">${totalBaseMV.toLocaleString()}</td>
            `;
        } else {
            tr.innerHTML = `<td>${item.StockTicker}</td><td>${item.SecurityName}</td><td>${parseFloat(item.Weightings).toFixed(2)}%</td>`;
        }

        totalWeight += parseFloat(item.Weightings) || 0;
        tbody.appendChild(tr);
    });

    const totalElem = document.getElementById(`${bucketId}-total`);
    if(totalElem) totalElem.textContent = totalWeight.toFixed(2) + '%';

    // Sum of Forgone Gains
    if(bucketId === 'options'){
        const tfootCell = document.querySelector('#options-table tfoot td:last-child');
        let forgoneSum = 0;
        data.forEach(item => {
            const strike = Number(item.Strike_Price);
            const opening = Number(item.OpeningPrice);
            const contracts = Number(item.Contracts);
            const totalBaseMV = Number(item.TotalBaseMV);
            if(strike < opening){
                forgoneSum += ((opening - strike) * 100 * contracts) / totalBaseMV * 100;
            }
        });
        if(tfootCell) tfootCell.textContent = forgoneSum.toFixed(2) + '%';
    }
}

// --- Sorting ---
document.querySelectorAll('th').forEach(th => {
    th.addEventListener('click', () => {
        const table = th.closest('table');
        const tbody = table.querySelector('tbody');
        const index = th.cellIndex;
        const type = th.dataset.type;
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const asc = th.classList.toggle('asc');

        rows.sort((a,b) => {
            let aText = a.cells[index].dataset.value || a.cells[index].textContent.replace(/,/g,'').replace('%','').trim();
            let bText = b.cells[index].dataset.value || b.cells[index].textContent.replace(/,/g,'').replace('%','').trim();
            if(type === 'number'){
                aText = parseFloat(aText) || 0;
                bText = parseFloat(bText) || 0;
            } else if(type === 'date'){
                aText = new Date(aText);
                bText = new Date(bText);
            }
            return aText < bText ? (asc?-1:1) : aText > bText ? (asc?1:-1) : 0;
        });

        tbody.innerHTML = '';
        rows.forEach(row => tbody.appendChild(row));
    });
});

// --- Update button ---
updateButton.addEventListener("click", () => {
    const userIndex = parseFloat(userIndexInput.value);
    if(isNaN(userIndex)) return alert("Enter a valid index value");

    const tbody = document.querySelector("#options-table tbody");
    const rows = tbody.querySelectorAll("tr");
    let forgoneSum = 0;

    rows.forEach(row => {
        const strike = parseFloat(row.cells[4].textContent.replace(/,/g,'')) || 0;
        const contracts = parseFloat(row.cells[9].textContent.replace(/,/g,'')) || 0;
        const totalBaseMV = parseFloat(row.cells[10].textContent.replace(/,/g,'')) || 1;

        const upside = (strike - userIndex) / userIndex * 100;
        row.cells[5].textContent = userIndex.toFixed(2);
        row.cells[6].textContent = upside.toFixed(2) + "%";

        let status = '', statusClass = '', forgone = 0;
        if(upside < 0){
            status = 'ITM';
            statusClass = 'itm';
            forgone = ((userIndex - strike) * 100 * contracts) / totalBaseMV * 100;
            row.cells[8].textContent = forgone.toFixed(2) + "%";
        } else {
            status = 'OTM';
            statusClass = 'otm';
            row.cells[8].textContent = '0.000%';
        }

        row.cells[7].textContent = status;
        row.cells[7].className = statusClass;
        forgoneSum += forgone;
    });

    const tfootCell = document.querySelector('#options-table tfoot td:last-child');
    if(tfootCell) tfootCell.textContent = forgoneSum.toFixed(2) + '%';
});
