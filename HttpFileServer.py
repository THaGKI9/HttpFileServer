#!/usr/bin/env python
# -*- coding:utf-8 -*-
import os
import socket
import sys
import cgi
import urllib

from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from SocketServer import ThreadingMixIn
from shutil import copyfileobj
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


class PartialContentHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        f = self.send_head()
        if f:
            self.copyfile(f, self.wfile)


    def list_directory(self, path):
        try:
            list = os.listdir(path)
        except os.error:
            self.send_error(404, "No permission to list directory")
            return None
        list.sort(key=lambda a: a.lower())
        f = StringIO()
        displaypath = cgi.escape(urllib.unquote(self.path))
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write("<html>\n<title>Directory listing for %s</title>\n" % displaypath)
        f.write("<body>\n<h2>Directory: %s</h2>\n" % os.path.join(path, displaypath))
        f.write("<hr>\n<ul>\n")
        
        files = ''
        dirs = ''
        for name in list:
            fullname = os.path.join(path, name)
            displayname = linkname = name
            # Append / for directories or @ for symbolic links
            isdir = os.path.isdir(fullname)
            if isdir:
                displayname = name + "/"
                linkname = name + "/"
            if os.path.islink(fullname):
                displayname = name + "@"
                # Note: a link to a directory displays with @ and links with /
            
            if isdir:
                dirs += '<li><a href="%s">%s</a>\n' % (urllib.quote(linkname), cgi.escape(displayname))
            else:
                files += '<li><a href="%s">%s</a>\n' % (urllib.quote(linkname), cgi.escape(displayname))
        f.write(dirs)
        if dirs and files:
            f.write('<hr>\n')
        f.write(files)
        if not (dirs or files):
            f.write('<li>Nothing Here\n')
        f.write("</ul>\n<hr>\n</body>\n</html>\n")
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=gb2312")
        self.send_header("Connection", "close")
        self.send_header("Content-Length", str(length))
        self.end_headers()  
        return f


    def send_head(self):
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            return self.list_directory(path)
                        
        elif not self.headers.get("Range"):
            return SimpleHTTPRequestHandler.send_head(self)
        
        else:
            ctype = self.guess_type(path)
            try:
                file = open(path, 'rb')
                fs = os.fstat(file.fileno())
                file_size = fs.st_size
                file_mtime = fs.st_mtime
            except IOError:
                self.send_error(404, "File not found")
                return None
            
            # it doesn't support 'suffix-byte-range-spec' right now(page 138)
            # only support bytes
            try:
                unit, range_set_raw = self.headers.get("Range").split('=', 1)
                if unit != 'bytes':
                    raise ValueError
                range_set = [i.split('-', 1) for i in range_set_raw.split(',', 1)]
                
                # not support multi range now
                if len(range_set) > 1:
                    raise ValueError
                
                # process ranges
                ranges = []
                for i in range_set:
                    if not i[0]:
                        # such as -500: means last 500 bytes
                        first_byte_pos = file_size - int(i[0])
                        last_byte_pos = file_size - 1
                    else:
                        # standard
                        first_byte_pos = int(i[0])
                        if first_byte_pos < 0:
                            raise ValueError
                        last_byte_pos = int(i[1]) if i[1] else file_size - 1
                        # interpret inlegal range as fully
                        if last_byte_pos >= file_size:
                            last_byte_pos = file_size

                    ranges.append([first_byte_pos, last_byte_pos, last_byte_pos - first_byte_pos + 1])
                
            except ValueError:
                self.send_error(400, "bad range specified.")
                file.close()
                return None

            self.send_response(206)
            self.send_header("Content-type", ctype)
            self.send_header("Connection", "close")
            self.send_header("Content-Length", str(ranges[0][2]))
            self.send_header("Last-Modified", self.date_time_string(file_mtime))
            # temporary support only one range
            self.send_header("Content-Range", "%s %d-%d/%d" % (unit, ranges[0][0], ranges[0][1], file_size))
            self.end_headers()

            # copy the partial file
            try:
                file.seek(ranges[0][0])
                f = StringIO()
                d = file.read(ranges[0][2])
                f.write(d)
                f.seek(0)
                self.log_message('"%s" %s', self.requestline, "req finished.")
            except socket.error:
                self.log_message('"%s" %s', self.requestline, "req terminated.")
            finally:
                file.close()
                
            return f



class MultiThreadServer(ThreadingMixIn, HTTPServer):
    """
    could make this a mixin, but decide to keep it simple for a simple script.
    """
    def _handle_error(self, *args):
        """override default function to disable traceback."""
        pass
    

if __name__ == "__main__":
    port = 80
    server_address = ('', port)
    s = MultiThreadServer(server_address, PartialContentHandler)
    sa = s.socket.getsockname()
    
    print "Serving HTTP on", sa[0], "port", sa[1], "..."
    s.serve_forever()
