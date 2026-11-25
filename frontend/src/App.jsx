import { useRef, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Cloud,
  Download,
  FileText,
  LoaderCircle,
  RotateCcw,
  Upload,
} from 'lucide-react'

const API = import.meta.env.DEV ? 'http://127.0.0.1:8000' : window.location.origin

export default function App() {
  const input = useRef(null)
  const [file, setFile] = useState(null)
  const [drag, setDrag] = useState(false)
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState(null)
  const [processed, setProcessed] = useState(null)
  const [error, setError] = useState('')
  const [downloadUrl, setDownloadUrl] = useState('')

  function reset() {
    setFile(null)
    setReport(null)
    setProcessed(null)
    setError('')
    if (downloadUrl) URL.revokeObjectURL(downloadUrl)
    setDownloadUrl('')
    if (input.current) input.current.value = ''
  }

  function selectFile(nextFile) {
    if (!nextFile) return
    if (!nextFile.name.toLowerCase().endsWith('.pdf')) {
      setError('Please select a PDF file.')
      return
    }
    setFile(nextFile)
    setReport(null)
    setProcessed(null)
    setError('')
    if (downloadUrl) URL.revokeObjectURL(downloadUrl)
    setDownloadUrl('')
  }

  async function processPdf() {
    if (!file || busy) return
    setBusy(true)
    setError('')
    setReport(null)
    setProcessed(null)

    try {
      const inspectData = new FormData()
      inspectData.append('file', file)
      let response = await fetch(`${API}/api/pdf/inspect`, {
        method: 'POST',
        body: inspectData,
      })
      if (!response.ok) {
        const body = await response.json()
        throw new Error(body.detail || 'PDF inspection failed.')
      }
      const inspection = await response.json()
      setReport(inspection)

      const processData = new FormData()
      processData.append('file', file)
      response = await fetch(`${API}/api/pdf/process`, {
        method: 'POST',
        body: processData,
      })
      if (!response.ok) {
        const body = await response.json()
        throw new Error(body.detail || 'PDF processing failed.')
      }

      const blob = await response.blob()
      const newUrl = URL.createObjectURL(blob)
      setDownloadUrl(newUrl)
      setProcessed({
        created: Number(response.headers.get('X-Repair-Created-Spans') ?? inspection.summary.ready_to_create_span ?? 0),
        unchanged: Number(response.headers.get('X-Repair-Unchanged-Spans') ?? inspection.summary.existing_span ?? 0),
        skipped: Number(response.headers.get('X-Repair-Skipped') ?? inspection.summary.skipped ?? 0),
      })
    } catch (err) {
      setError(`${err.message} Confirm that the backend is running at ${API}.`)
    } finally {
      setBusy(false)
    }
  }

  const summary = report?.summary

  return (
    <main className="page">
      <section className="card">
        <h1>Upload your PDF</h1>
        <p className="intro">
          Choose a PDF from your computer, or drag and drop it into the upload area.
        </p>

        <div
          className={`drop ${drag ? 'drag' : ''}`}
          onDragOver={(event) => { event.preventDefault(); setDrag(true) }}
          onDragLeave={() => setDrag(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDrag(false)
            selectFile(event.dataTransfer.files?.[0])
          }}
        >
          <input
            ref={input}
            hidden
            type="file"
            accept=".pdf,application/pdf"
            onChange={(event) => selectFile(event.target.files?.[0])}
          />
          {file ? (
            <FileText size={48} className="fileicon" />
          ) : (
            <div className="art"><Cloud size={42} /><Upload size={42} className="upicon" /></div>
          )}
          <strong>{file ? file.name : 'Drag and drop your PDF here'}</strong>
          <span>{file ? `${(file.size / 1048576).toFixed(2)} MB · PDF selected` : 'PDF files only'}</span>
          <button className="browse" type="button" onClick={() => input.current?.click()}>
            Browse files
          </button>
        </div>

        {error && <div className="error"><AlertCircle size={18} />{error}</div>}

        <div className="actions">
          <button className="process" disabled={!file || busy} onClick={processPdf}>
            {busy ? <><LoaderCircle className="spin" size={18} /> Processing PDF...</> : 'Process PDF'}
          </button>
          <button className="reset" onClick={reset}><RotateCcw size={15} /> Reset</button>
        </div>

        {report && (
          <section className="results">
            <div className="resulthead"><CheckCircle2 /><h2>{downloadUrl ? 'PDF processed successfully' : 'PDF inspection complete'}</h2></div>
            <p className="meta">{report.filename} · {report.pages} pages · {report.is_tagged ? 'Tagged PDF' : 'Not tagged'}</p>

            <div className="stats">
              <div><b>{report.label_count}</b><span>Lbl tags</span></div>
              <div><b>{processed?.unchanged ?? summary.existing_span}</b><span>Existing Span preserved</span></div>
              <div><b>{processed?.created ?? summary.ready_to_create_span}</b><span>Span created</span></div>
              <div><b>{processed?.skipped ?? summary.skipped}</b><span>Skipped</span></div>
            </div>

            {downloadUrl && (
              <a
                className="download"
                href={downloadUrl}
                download={`${file.name.replace(/\.pdf$/i, '')}_actual_text.pdf`}
              >
                <Download size={18} /> Download processed PDF
              </a>
            )}

            <h3>Label inspection details</h3>
            <div className="list">
              {report.labels.map((item) => (
                <div className="item" key={item.index}>
                  <b>Lbl {item.index}</b>
                  <span className={item.status}>{item.status.replaceAll('_', ' ')}</span>
                  <small>{item.detail}</small>
                </div>
              ))}
            </div>
            <p className="note">
              Existing Span elements are preserved. New spans are created only after
              confirming the bullet marked content and its ParentTree relationship.
            </p>
          </section>
        )}
      </section>
      <footer>Actual Text PDF · Accessible document processing</footer>
    </main>
  )
}
