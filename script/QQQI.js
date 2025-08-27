const buckets = [
    { id: 'options', prefix: '../data/QQQI-Files/QQQI_Options_-_Index_' },
    { id: 'cash',    prefix: '../data/QQQI-Files/QQQI_Cash_' },
    { id: 'stocks',  prefix: '../data/QQQI-Files/QQQI_Stocks_' }
];

const dateSelect = document.getElementById("dateSelect");

// Load available dates and populate dropdown
fetch("../data/QQQI-Files/available_dates.json")
  .then(res => res.json())
  .then(data => {
      data.dates.forEach(date => {
          const opt = document.createElement("option");
          opt.value = date;
          opt.textContent = date;
          dateSelect.appendChild(opt);
      });

      // Default: last date (latest available)
      dateSelect.value = data.dates[data.dates.length - 1];
      loadTables(dateSelect.value);
  })
  .catch(err => console.error("Failed to load available_dates.json:", err));

// When user selects a date
dateSelect.addEventListener("change", () => {
    loadTables(dateSelect.value);
});

function loadTables(date) {
    const timestamp = new Date().getTime(); // cache-busting
    
    buckets.forEach(bucket => {
        const file = `${bucket.prefix}${date}.json?ts=${timestamp}`; // cache-busting
        fetch(file)
          .then(res => res.json())
          .then(data => {
              const tbody = document.querySelector(`#${bucket.id}-table tbody`);
              tbody.innerHTML = ""; // clear old data
              let totalWeight = 0;

              if (data.length === 0) {
                  const tr = document.createElement('tr');
                  const td = document.createElement('td');
                  td.colSpan = bucket.id === 'options' ? 8 : 2;
                  td.textContent = "No records available";
                  tr.appendChild(td);
                  tbody.appendChild(tr);
                  return;
              }

              data.forEach(item => {
                  const tr = document.createElement('tr');
                  if(bucket.id === 'options') {
                      const [year, month, day] = item.Expiry_Date.split('-');
                      const displayDate = `${day}/${month}/${year}`;
                      const strike = parseFloat(item.Strike_Price.replace(/,/g, ''));
                      const opening = parseFloat(item.OpeningPrice);
                      const upside = (strike - opening) / opening * 100;
                      let status = '', statusClass = '', forgoneGains = '';

                      if (upside < 0) {
                          status = 'ITM';
                          statusClass = 'itm';
                          forgoneGains = (parseFloat(item.ForgoneGainPct) * 100).toFixed(2) + '%';
                      } else {
                          status = 'OTM';
                          statusClass = 'otm';
                          forgoneGains = 0.00 + '%';
                      }

                      tr.innerHTML = `
                          <td>${item.StockTIcker}</td>
                          <td>${item.Weightings}%</td>
                          <td data-value="${item.Expiry_Date}">${displayDate}</td>
                          <td>${item.Strike_Price}</td>
                          <td>${item.OpeningPrice}</td>
                          <td>${upside.toFixed(2)}%</td>
                          <td class="${statusClass}">${status}</td>
                          <td>${forgoneGains}</td>
                      `;
                  } else {
                      tr.innerHTML = `<td>${item.StockTIcker}</td><td>${item.Weightings}%</td>`;
                  }

                  totalWeight += parseFloat(item.Weightings) || 0;
                  tbody.appendChild(tr);
              });

              document.getElementById(`${bucket.id}-total`).textContent = totalWeight.toFixed(2) + '%';

              // Sum of all Forgone Gains for options table
              if(bucket.id === 'options') {
                  const tfootCell = document.querySelector('#options-table tfoot td:last-child');
                  const forgoneCells = document.querySelectorAll('#options-table tbody td:nth-child(8)');
                  let forgoneSum = 0;
                  forgoneCells.forEach(td => {
                      const val = parseFloat(td.textContent.replace('%',''));
                      if(!isNaN(val)) forgoneSum += val;
                  });
                  tfootCell.textContent = forgoneSum.toFixed(2) + '%';
              }
          })
          .catch(err => console.error(`Failed to load ${file}:`, err));
    });
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

            if(type === 'number') {
                aText = parseFloat(aText) || 0;
                bText = parseFloat(bText) || 0;
            } else if(type === 'date') {
                aText = new Date(aText);
                bText = new Date(bText);
            }

            if(aText < bText) return asc ? -1 : 1;
            if(aText > bText) return asc ? 1 : -1;
            return 0;
        });

        tbody.innerHTML = '';
        rows.forEach(row => tbody.appendChild(row));
    });
});
