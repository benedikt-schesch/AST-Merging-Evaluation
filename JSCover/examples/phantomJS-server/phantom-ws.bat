rem Make sure phantomjs is on your execution PATH
PUSHD ..\..
phantomjs src\test\javascript\lib\PhantomJS\run-jscover-qunit.js http://localhost:8080/test/index.html
POPD