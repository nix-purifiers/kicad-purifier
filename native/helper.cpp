#include "pcm.h"
#include <build_version.h>
#include <wx/tokenzr.h>
#include <fstream>
#include <wx/sstream.h>
#include "headless.hpp"

const std::tuple<int, int, int> PLUGIN_CONTENT_MANAGER::m_kicad_version =
        GetMajorMinorPatchTuple();

class Thrower : public nlohmann::json_schema::error_handler
{
    void error( const nlohmann::json::json_pointer& pointer, const nlohmann::json&,
                const std::string& message ) override
    {
        throw std::invalid_argument( pointer.to_string() + ": " + message );
    }
};

int main( int argc, char** argv )
{
    if( argc != 3 && argc != 4 && argc != 7 )
        return 2;
    try
    {
        if( argc == 3 && std::string( argv[1] ) == "register" )
        {
            std::ifstream input( argv[2] );
            nlohmann::json lock;
            input >> lock;
            nlohmann::json packages = nlohmann::json::array();
            for( const auto& selected : lock.at( "entries" ) )
            {
                PCM_INSTALLATION_ENTRY entry {};
                entry.package = lock.at( "native" ).at( "catalog" ).at(
                    selected.at( "path" ).get<std::string>() ).get<PCM_PACKAGE>();
                PLUGIN_CONTENT_MANAGER::PreparePackage( entry.package );
                entry.current_version = wxString::FromUTF8(
                    selected.at( "kicad" ).at( "version" ).get<std::string>() );
                entry.repository_id = "nix-purifier";
                entry.repository_name = "Nix-locked KiCad plugins";
                entry.install_timestamp = 1;
                entry.pinned = true;
                packages.push_back( nlohmann::json( entry ) );
            }
            std::cout << nlohmann::json( { { "packages", packages } } ).dump() << std::endl;
            return 0;
        }
        if( argc == 4 && std::string( argv[1] ) == "repository" )
        {
            std::ifstream input( argv[2] );
            nlohmann::json data;
            input >> data;
            JSON_SCHEMA_VALIDATOR validator( wxFileName( wxString::FromUTF8( argv[3] ) ) );
            Thrower handler;
            validator.Validate( data, handler, nlohmann::json_uri( "#/definitions/Repository" ) );
            PCM_REPOSITORY repository = data.get<PCM_REPOSITORY>();
            std::cout << nlohmann::json( repository ).dump() << std::endl;
            return 0;
        }
        if( argc == 7 && std::string( argv[1] ) == "install" )
        {
            wxFFileInputStream stream( wxString::FromUTF8( argv[2] ) );
            wxZipInputStream zip( stream );
            nlohmann::json metadata;
            for( std::unique_ptr<wxZipEntry> entry( zip.GetNextEntry() ); entry;
                 entry.reset( zip.GetNextEntry() ) )
            {
                if( entry->GetName().StartsWith( "plugins/" )
                    && entry->GetName().EndsWith( "/plugin.json" ) )
                    throw std::runtime_error( "IPC plugin descriptors need a managed-environment provider" );
                if( entry->GetName() != "metadata.json" )
                    continue;
                wxStringOutputStream contents;
                if( !CopyStreamData( zip, contents, entry->GetSize() ) )
                    throw std::runtime_error( "cannot read native archive metadata" );
                metadata = nlohmann::json::parse( contents.GetString().ToUTF8().data() );
            }
            JSON_SCHEMA_VALIDATOR validator( wxFileName( wxString::FromUTF8( argv[6] ) ) );
            Thrower handler;
            validator.Validate( metadata, handler );
            PCM_PACKAGE package = metadata.get<PCM_PACKAGE>();
            PLUGIN_CONTENT_MANAGER::PreparePackage( package );
            if( package.identifier != wxString::FromUTF8( argv[4] ) || package.versions.size() != 1
                || package.versions[0].version != wxString::FromUTF8( argv[5] )
                || !package.versions[0].compatible || package.type != PT_PLUGIN
                || ( package.versions[0].runtime
                     && *package.versions[0].runtime != PCM_PACKAGE_RUNTIME::PPR_SWIG ) )
                throw std::runtime_error( "archive identity, version, compatibility or runtime mismatch" );
            Destination destination { wxString::FromUTF8( argv[3] ) };
            HeadlessReporter reporter;
            PCM_TASK_MANAGER task { &destination, &reporter };
            return task.extract( wxString::FromUTF8( argv[2] ),
                                 wxString::FromUTF8( argv[4] ), true ) ? 0 : 1;
        }
        std::ifstream input( argv[1] );
        nlohmann::json data;
        input >> data;
        JSON_SCHEMA_VALIDATOR validator( wxFileName( wxString::FromUTF8( argv[2] ) ) );
        Thrower handler;
        validator.Validate( data, handler, nlohmann::json_uri( "#/definitions/PackageArray" ) );
        nlohmann::json result = nlohmann::json::array();
        for( const auto& entry : data.at( "packages" ) )
        {
            PCM_PACKAGE package = entry.get<PCM_PACKAGE>();
            PLUGIN_CONTENT_MANAGER::PreparePackage( package );
            nlohmann::json versions = nlohmann::json::array();
            for( const auto& version : package.versions )
                versions.push_back( { { "metadata", nlohmann::json( version ) },
                                      { "compatible", version.compatible } } );
            result.push_back( { { "id", package.identifier }, { "versions", versions } } );
        }
        std::cout << result.dump() << std::endl;
    }
    catch( const std::exception& error )
    {
        std::cerr << error.what() << std::endl;
        return 1;
    }
}
