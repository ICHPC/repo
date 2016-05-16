#!/usr/local/python/bin/python
from psycopg2 import *
from psycopg2.extras import *
from lxml.etree import *
import re
import configparser
import requests
import base64
import sys
import os


def update_files( con, doi, full_doi, doiauth, files ):
			headers={
				'Content-Type' : "application/xml;charset=UTF-8",
				"Authorization" : "Basic " +  doiauth 
			}
			x=0
			for f in files:
				sanitisefn = re.sub( "[ ><,+!'()&%$/;:]", "_", f['filename'] )
				key = f['mimetype'] + "+" + sanitisefn
				key = key.lower()
				value = "https://data.hpc.imperial.ac.uk/resolve/?doi=" + str(doi) + "&file=" + str(x)
				md = key + "=" + value
				x=x+1
				r = requests.post( "https://mds.datacite.org/media/" + full_doi, headers= headers, data = md )
				
				print(" - POST MEDIA"  )
				if(  r.status_code != requests.codes.ok ):
					print( "ERROR: Status code:" + str( r.status_code) )
					print( "REQUEST  : " + md )
					print( "RESPONSE : " + r.content.decode("ascii"))
					return False

			return True

def update_metadata( con, doi, full_doi, doiauth, md ):
			headers={
				'Content-Type' : "application/xml;charset=UTF-8",
				"Authorization" : "Basic " +  doiauth 
			}
		#	print(headers)
			r = requests.post( "https://mds.datacite.org/metadata", headers= headers, data = md )

			print(" - POST METADATA")

#			r2 = requests.get( "https://mds.datacite.org/metadata/" + full_doi, headers=headers );
#			print(r2.content.decode("ascii"))
			if(  r.status_code > 201 ):
				print("ERROR: Status code:" + str( r.status_code) )
				print( "RESPONSE\n" + r.content.decode("ascii"))
				return False
			else:
				return True

			
#		sys.exit(0)


def get_heirarchy( con, doi ):
	cur = con.cursor( cursor_factory = RealDictCursor )
	cur.execute( "SELECT child FROM membership WHERE parent=%s", [doi]  )
	children = cur.fetchall()
	cur.close()

	cur = con.cursor( cursor_factory = RealDictCursor )
	cur.execute( "SELECT parent FROM membership WHERE child=%s", [doi]  )
	parents = cur.fetchall()
	cur.close()
	return  { "parents": parents, "children" : children }

def get_assoc( con, doi ):
	cur = con.cursor( cursor_factory = RealDictCursor )
	cur.execute( "SELECT * FROM associated WHERE doi = %s ORDER BY associated ASC", [doi]  )
	ret = cur.fetchall()
	cur.close()
	return ret




def get_collaborators( con, doi ):
	cur = con.cursor( cursor_factory = RealDictCursor )
	cur.execute( "SELECT * FROM collaboration A LEFT JOIN account B on A.user_id = B.user_id WHERE A.doi = %s", [doi]  )
	ret = cur.fetchall()
	cur.close()
	return ret

def get_files( con, doi ):
	cur = con.cursor( cursor_factory = RealDictCursor )
	cur.execute( "SELECT * FROM file WHERE doi = %s ORDER BY seq ASC", [doi]  )
	ret = cur.fetchall()
	cur.close()
	return ret


def get_metadata( con, doi ):
	cur = con.cursor( cursor_factory = RealDictCursor )
	cur.execute( "SELECT * FROM metadata WHERE doi = %s ORDER BY key ASC", [doi]  )
	ret = cur.fetchall()
	cur.close()
	return ret

#<ns0:resource xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:ns0="http://datacite.org/schema/kernel-2.2" xsi:schemaLocation="http://datacite.org/schema/kernel-2.2 http://schema.datacite.org/meta/kernel-2.2/metadata.xsd">


def create_metadata( doi_prefix,record, collabs, files, metadata , heir, assoc ):
	doi = doi_prefix + str(record['doi'])
	ns = "http://datacite.org/schema/kernel-3"
	xsi="http://www.w3.org/2001/XMLSchema-instance"
	resource =  Element(  '{'+ns+'}resource', nsmap={ None:ns, "xsi":xsi } )
	
	resource.set( "{" + xsi+ "}schemaLocation", "http://datacite.org/schema/kernel-3 http://schema.datacite.org/meta/kernel-3/metadata.xsd" )
	identifier = Element( "identifier" );
	identifier.text = doi
	identifier.set( "identifierType", "DOI" )
	resource.append( identifier )

	creators = SubElement( resource, "creators" );

	creator = SubElement( creators, "creator" )
	SubElement( creator, "creatorName" ).text = record['name']
	ni = SubElement( creator, "nameIdentifier" )
	ni.set( "schemeURI", "http://orcid.org" )
	ni.set( "nameIdentifierScheme", "ORCID" )
	ni.text = record['orcid']
	SubElement( creator, "affiliation" ).text = "Imperial College London"

	contributors = SubElement( resource, "contributors" )
	contributor = SubElement( contributors, "contributor" )
	contributor.set( "contributorType", "HostingInstitution" )
	SubElement( contributor, "contributorName" ).text = "Imperial College High Performance Computing Service"
	
	for rec in collabs:
		contributor = SubElement( contributors, "contributor" )
		contributor.set( "contributorType", "Researcher" )
		SubElement( contributor, "contributorName" ).text = rec['name']
#	SubElement( contributor, "affiliation" ).text = "Imperial College London"
		ni = SubElement( contributor , "nameIdentifier" )
		ni.set( "schemeURI", "http://orcid.org" )
		ni.set( "nameIdentifierScheme", "ORCID" )
		ni.text = record['orcid']
		SubElement( contributor, "affiliation" ).text = "Imperial College London"

	descriptions= SubElement( resource, "descriptions" )
	description = SubElement( descriptions, "description" )
	description.text = record['description']
	description.set( "descriptionType", "Other" )

	titles = SubElement( resource, "titles" )
	SubElement( titles, "title" ).text = record['title']
	SubElement( resource, "publisher" ).text="Imperial College London" 
	SubElement( resource, "publicationYear").text = str( record['creation_date'].timetuple().tm_year )
	dds= SubElement( resource, "dates" )
	dd = SubElement( dds, "date")
	dd.text = str( record['creation_date'] )
	dd.set( "dateType", "Created" )

	relateds = SubElement( resource, "relatedIdentifiers" )
	related  = SubElement( relateds, "relatedIdentifier" )
	related.set( "relatedIdentifierType", "URL" )
	related.set( "relationType", "HasMetadata" )
	related.set( "relatedMetadataScheme", "ORE" )
	related.set( "schemeURI", "http://www.openarchives.org/ore/" )
	related.text="https://data.hpc.imperial.ac.uk/resolve/?ore=" + str(record['doi'])

	for f in files:
		related  = SubElement( relateds, "relatedIdentifier" )
		related.set( "relatedIdentifierType", "URL" )
		related.set( "relationType", "HasPart" )
		related.set( "relatedMetadataScheme", "Filename" )
		related.set( "schemeURI", "mime+filename://" + f['mimetype'] + "+" + f['filename'] )
		related.text="https://data.hpc.imperial.ac.uk/resolve/?doi=" + str(record['doi']) + "&file=" + str(f['seq'])

	subjects = SubElement( resource, "subjects" )
	for a in metadata:
		subject = SubElement( subjects, "subject" )
		subject.text = a['value']
		subject.set( "subjectScheme", a['key'] )

	for a in assoc:
		if a['associated']:
			related  = SubElement( relateds, "relatedIdentifier" )
			related.set( "relatedIdentifierType", "DOI" )
			related.set( "relationType", "IsReferencedBy" )
			related.text= a['associated']
		


	children = heir['children']
	parents  = heir['parents']	
	for p in parents:
		related  = SubElement( relateds, "relatedIdentifier" )
		related.set( "relatedIdentifierType", "DOI" )
		related.set( "relationType", "IsPartOf" )
		related.text= doi_prefix + str(p['parent'])
	for p in children:
		related  = SubElement( relateds, "relatedIdentifier" )
		related.set( "relatedIdentifierType", "DOI" )
		related.set( "relationType", "HasPart" )
		related.text= doi_prefix + str(p['child'])




		

	rightslist = SubElement( resource, "rightsList" )
	rights     = SubElement( rightslist, "rights" )
	rights.set("rightsURI", "https://creativecommons.org/publicdomain/zero/1.0/");
	rights.text="Creative Commons Public Domain Dedication (CC0 1.0)"

	resourcetype = SubElement( resource, "resourceType" )

	if( record['collection'] ):
		resourcetype.set( "resourceTypeGeneral", "Collection" )
	else:
		resourcetype.set( "resourceTypeGeneral", "Dataset" )


	return tostring( resource, pretty_print=True ).decode("utf-8")



if __name__ == "__main__":
	
	cp = configparser.ConfigParser( interpolation=None )
	cp.read('/var/www/data.hpc.imperial.ac.uk/repo/configuration.ini' )


	doi_prefix = re.sub( '"', '', cp.get( "datacite", "dc_prefix")) 
	doi_user   = re.sub( '"', '', cp.get( "datacite", "dc_user")) 
	doi_pass   = re.sub( '"', '', cp.get( "datacite", "dc_password"))
	db_name    = re.sub( '"', '', cp.get( "database", "db_dbname" ))
	db_user    = re.sub( '"', '', cp.get( "database", "db_user" ))
	db_host    = re.sub( '"', '', cp.get( "database", "db_host" ))
	db_password= re.sub( '"', '', cp.get( "database", "db_password" ))
	
	con = connect("dbname='%s' user='%s' host='%s' password='%s'" % ( db_name, db_user, db_host, db_password) )
	cur = con.cursor( cursor_factory = RealDictCursor )
	cur.execute("SELECT * FROM doi A LEFT JOIN account B ON A.creator = B.user_id WHERE A.embargoed = FALSE AND A.updated = TRUE ORDER BY doi ASC")

	row=cur.fetchall()
	for a in row:
##		try:
			doi=int(a['doi'])
			collabs = get_collaborators( con, doi ) 
			files   = get_files( con, doi )
			metadata= get_metadata( con, doi )
			heirarchy=get_heirarchy( con, doi )
			assoc    =get_assoc( con, doi )
#		print(collabs)
#		print(files)
#		print(metadata)

			doiauth = base64.b64encode( (doi_user + ":" + doi_pass).encode("ascii") )
			doiauth = doiauth.decode("ascii")
			full_doi = doi_prefix + str(a['doi'])

			print("=== Updating metadata for DOI " + full_doi )

			md = create_metadata( doi_prefix , a, collabs, files, metadata, heirarchy, assoc )

			print(md)

			ret1 = update_files   ( con, doi, full_doi, doiauth, files )
			ret2 = update_metadata( con, doi, full_doi, doiauth, md )

			if( ret1 and ret2 ):
				print(" - MARKING COMPLETE" )
				cur = con.cursor( cursor_factory = RealDictCursor )
				cur.execute("UPDATE doi SET updated = FALSE WHERE doi=%s", [ doi ] )
				cur.close()
				con.commit()


#		except:
#			raise
	
	cur.close()

