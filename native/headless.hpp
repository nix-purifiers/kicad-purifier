#pragma once
#include "pcm.h"
#include <widgets/report_severity.h>
#include <wx_filename.h>
#include <wxstream_helper.h>
#include <wx/dir.h>
#include <wx/wfstream.h>
#include <wx/zipstrm.h>

// Supply progress reporting and destination binding to the unchanged native extractor.
struct HeadlessReporter
{
    void PCMReport( const wxString& message, SEVERITY severity )
    {
        if( severity == RPT_SEVERITY_ERROR )
            throw std::runtime_error( message.ToStdString() );
    }
    void SetPackageProgress( int, int ) {}
    void KeepRefreshing( bool ) {}
    bool IsCancelled() { return false; }
};

struct Destination
{
    wxString path;
    wxString Get3rdPartyPath() const { return path; }
};

class PCM_TASK_MANAGER
{
public:
    Destination* m_pcm;
    HeadlessReporter* m_reporter;
    bool extract( const wxString&, const wxString&, bool );
};
