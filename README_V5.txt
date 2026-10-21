Dhruva Care v5 — complete project (everything integrated)
=========================================================
Run:  python app.py      (or ./run_dhruva_care.sh)   ->  http://localhost:5050

WHAT'S IN IT
 * One screen per feature (symptoms, doctors, pharmacy, diet, hospitals, teleconsult, fund) with next/prev slides.
 * Four separate login pages  (#login-patient / #login-doctor / #login-hospital / #login-admin):
     Patient  : email + password
     Doctor   : SMC number + NMR ID/UID + password   (register adds specialization, certificate, photo, hospital)
     Hospital : registration/licence no + HFR ID + password (register adds optional: affiliated to, departments, emergency)
     Admin    : email + password + Admin ID code
 * Doctor shows "Available" only when doctor AND hospital desk both mark presence today.
 * Hospital desk queue: walk-ins + online bookings; patients see their live position.
 * Doctors request access by Patient ID; patient approves/revokes; only then records are visible.
 * Support tickets (patients, doctors, hospitals) answered by admins.

DEMO LOGINS (this folder's data/ was seeded with them; password for all: Demo@12345)

== Hospitals  (license no + HFR ID + password) ==
  Hillside Care Hospital                   SK-HOSP-91     HFR-DEMO-0001
  Arunachal MediApp Partner Hospital       AR-HOSP-104    HFR-DEMO-0002
  Brahmaputra Healthcare & Diagnostics     ASM-HOSP-512   HFR-DEMO-0003

== Doctors  (SMC no + NMR ID + password) ==
  Dr. Ananya Baruah        ASM-MED-4412   NMR-DEMO-00001   hospital=hsp_guwahati01
  Dr. Taba Taku            AR-CARD-3301   NMR-DEMO-00002   hospital=hsp_itanagar01
  Dr. Patricia Lyngdoh     ML-DERM-0912   NMR-DEMO-00003   hospital=None
  Dr. Robert Singh         MAN-PED-1180   NMR-DEMO-00004   hospital=None
  Dr. Lipok Jamir          NL-ORTH-5120   NMR-DEMO-00005   hospital=None

== Patient ==
  demo.patient@dhruvacare.in   Patient ID PT-4BD7311D

All demo passwords: Demo@12345

 Admin: admin@dhruvacare.in / AdminDC#2026 / Admin ID code DC-ADMIN-2026   (override with DHRUVA_CARE_ADMIN_EMAIL, _PASSWORD, _CODE)

BEFORE REAL USE: delete the demo accounts (or restore data/ from your original), change the admin password and code.
