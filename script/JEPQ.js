const buckets = [
    { id: 'options', prefix: '/JEPQ/data/JEPQ-Files/JEPQ_Options_-_Index_' },
    { id: 'cash',    prefix: '/JEPQ/data/JEPQ-Files/JEPQ_Cash_' },
    { id: 'stocks',  prefix: '/JEPQ/data/JEPQ-Files/JEPQ_Stocks_' }
];

const dateSelect = document.getElementById("dateSelect");
const updateButton = document.getElementById("updateIndex");
const userIndexInput = document.getElementById("userIndex");

// Load available dates
fetch("/JEPQ/data/JEPQ-Files/available_dates.json")
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

        if (bucketId === 'options') {
            const [year, month, day] = item.Expiry_Date.split('-');
            const expiryDate = new Date(`${year}-${month}-${day}`);
            const displayDate = `${day}/${month}/${year}`;

            const tdte = Math.max(
                0,
                Math.round((expiryDate - today) / (1000 * 60 * 60 * 24) * 5 / 7)
            );

            const strike = parseFloat(item.Strike_Price.replace(/,/g, ''));
            const opening = parseFloat(item.OpeningPrice);
            const contracts = parseFloat(item.Contracts);
            const totalBaseMV = parseFloat(item.TotalBaseMV);

            const upside = (strike - opening) / opening * 100;

            console.log({
    ticker: row.cells[0].textContent,
    strike,
    contracts,
    totalBaseMV
});


            // ✅ Portfolio % Covered (NEW)
            const portfolioCoveredPct =
                (contracts * strike * 100) / totalBaseMV;

            let status = '';
            let statusClass = '';
            let forgoneGains = '';

            if (upside < 0) {
                status = 'ITM';
                statusClass = 'itm';
                forgoneGains = (parseFloat(item.ForgoneGainPct) * 100).toFixed(2) + '%';
            } else {
                status = 'OTM';
                statusClass = 'otm';
                forgoneGains = '0.00%';
            }

            tr.innerHTML = `
                <td>${item.Ticker}</td>
                <td>${portfolioCoveredPct.toFixed(2)}%</td>
                <td data-value="${item.Expiry_Date}">${displayDate}</td>
                <td>${tdte}</td>
                <td>${item.Strike_Price}</td>
                <td>${item.OpeningPrice}</td>
                <td>${upside.toFixed(2)}%</td>
                <td class="${statusClass}">${status}</td>
                <td>${forgoneGains}</td>
                <td style="display:none;">${item.Contracts}</td>
                <td style="display:none;">${item.TotalBaseMV}</td>
            `;

            totalWeight += portfolioCoveredPct;

        } else {
            // Cash & Stocks unchanged
            tr.innerHTML = `
                <td>${item.Ticker}</td>
                <td>${item.Weight}%</td>
            `;

            totalWeight += parseFloat(item.Weight) || 0;
        }

        tbody.appendChild(tr);
    });

    const totalElem = document.getElementById(`${bucketId}-total`);
    if (totalElem) {
        totalElem.textContent = totalWeight.toFixed(2) + '%';
    }
}

// ----- Sorting -----
document.querySelectorAll('th').forEach(th => {
    th.addEventListener('click', () => {
        const table = th.closest('table');
        const tbody = table.querySelector('tbody');
        const index = th.cellIndex;
        const type = th.dataset.type;
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const asc = th.classList.toggle('asc');

        rows.sort((a, b) => {
            let aText = a.cells[index].dataset.value || a.cells[index].textContent.trim().replace('%','');
            let bText = b.cells[index].dataset.value || b.cells[index].textContent.trim().replace('%','');

            if (type === 'number') {
                aText = parseFloat(aText.replace(/,/g,'')) || 0;
                bText = parseFloat(bText.replace(/,/g,'')) || 0;
            } else if (type === 'date') {
                aText = new Date(aText);
                bText = new Date(bText);
            }

            return aText < bText ? (asc ? -1 : 1)
                 : aText > bText ? (asc ? 1 : -1)
                 : 0;
        });

        tbody.innerHTML = '';
        rows.forEach(row => tbody.appendChild(row));
    });
});

// ----- Update Upside % and Forgone Gains -----
updateButton.addEventListener("click", () => {
    const userIndex = parseFloat(userIndexInput.value);
    if (isNaN(userIndex)) return alert("Enter a valid index value");

    const tbody = document.querySelector("#options-table tbody");
    const rows = tbody.querySelectorAll("tr");
    let forgoneSum = 0;

    rows.forEach(row => {
        const strike = parseFloat(row.cells[4].textContent.replace(/,/g,''));
        const contracts = parseFloat(row.cells[9].textContent.replace(/,/g,''));
        const totalBaseMV = parseFloat(row.cells[10].textContent);

        const upside = (strike - userIndex) / userIndex * 100;

        row.cells[5].textContent = userIndex.toFixed(2);
        row.cells[6].textContent = upside.toFixed(2) + "%";

        let status = '';
        let statusClass = '';
        let forgone = 0;

        if (upside < 0) {
            status = 'ITM';
            statusClass = 'itm';
            forgone = ((userIndex - strike) * contracts) / totalBaseMV * 100;
            row.cells[8].textContent = forgone.toFixed(2) + "%";
        } else {
            status = 'OTM';
            statusClass = 'otm';
            row.cells[8].textContent = '0.00%';
        }

        row.cells[7].textContent = status;
        row.cells[7].className = statusClass;

        forgoneSum += forgone;
    });

    const tfootCell = document.querySelector('#options-table tfoot td:last-child');
    if (tfootCell) {
        tfootCell.textContent = forgoneSum.toFixed(2) + '%';
    }
});
